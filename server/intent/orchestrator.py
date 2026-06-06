from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from server.adapters import DeviceController, LLMClient, RouterController, ToolCall
from server.intent.tools import SYSTEM_PROMPT, TOOLS


@dataclass
class TurnResult:
    """一轮对话的结果：识别文本、最终回复文本、本轮执行的动作列表。"""

    transcript: str
    reply_text: str
    actions: list[dict[str, Any]] = field(default_factory=list)


class IntentOrchestrator:
    """意图编排器（单轮）：拿到用户文本 → 问 LLM → 执行 LLM 要求的工具调用 →
    汇总出一句最终回复。

    暂不保存多轮对话记忆——每次请求都是独立的，这样模型成本低、也更好调试。
    """

    def __init__(
        self,
        llm: LLMClient,
        devices: DeviceController,
        router: RouterController,
    ) -> None:
        self._llm = llm
        self._devices = devices
        self._router = router

    async def handle_text(self, user_text: str) -> TurnResult:
        # 空文本（例如没识别到内容）直接给兜底回复
        if not user_text.strip():
            return TurnResult(transcript="", reply_text="我没听清，请再说一遍。")

        # 组装 system + user 两条消息，连同工具清单一起交给 LLM
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        response = await self._llm.chat(messages, tools=TOOLS)
        actions: list[dict[str, Any]] = []

        if response.tool_calls:
            # LLM 要求调用工具：逐个执行并收集结果，再据此组织回复
            for call in response.tool_calls:
                outcome = await self._dispatch(call)
                actions.append(outcome)
            reply = self._format_reply(actions, response.text)
        else:
            # LLM 只回了文字、没调工具
            reply = response.text or "好的。"

        return TurnResult(transcript=user_text, reply_text=reply, actions=actions)

    async def _dispatch(self, call: ToolCall) -> dict[str, Any]:
        # 把一次工具调用路由到对应的设备/路由器操作，统一返回 {tool, ok, ...} 结构
        logger.info("dispatch tool={} args={}", call.name, call.arguments)
        try:
            if call.name == "set_device_state":
                # 把 device_id 单独取出，其余字段作为要写入的状态
                device_id = call.arguments.get("device_id", "")
                fields = {k: v for k, v in call.arguments.items() if k != "device_id"}
                snapshot = self._devices.set_state(device_id, **fields)
                return {"tool": call.name, "ok": True, "device": snapshot}
            if call.name == "list_devices":
                return {"tool": call.name, "ok": True, "devices": self._devices.list_devices()}
            if call.name == "router_reboot":
                msg = await self._router.reboot()
                return {"tool": call.name, "ok": True, "message": msg}
            if call.name == "router_restart_wifi":
                msg = await self._router.restart_wifi()
                return {"tool": call.name, "ok": True, "message": msg}
            return {"tool": call.name, "ok": False, "error": "unknown tool"}
        except Exception as e:
            # 任一工具执行抛错都在此兜住，转成 ok=False 的结果，不让整轮请求崩溃
            logger.exception("tool {} failed", call.name)
            return {"tool": call.name, "ok": False, "error": str(e)}

    def _format_reply(self, actions: list[dict[str, Any]], llm_text: str) -> str:
        # 优先用 LLM 自己给出的回复文本
        if llm_text.strip():
            return llm_text.strip()

        # LLM 没给文字时，根据工具执行结果自行拼一句话播报
        successes = [a for a in actions if a.get("ok")]
        failures = [a for a in actions if not a.get("ok")]

        parts: list[str] = []
        for a in successes:
            tool = a["tool"]
            if tool == "set_device_state":
                dev = a["device"]
                parts.append(f"{dev['name']} 已设置为 {dev.get('state', '')}")
            elif tool == "list_devices":
                names = [d["name"] for d in a["devices"]]
                parts.append("当前接入的设备有：" + "、".join(names))
            elif tool == "router_reboot":
                parts.append(a.get("message", "路由器重启已发送"))
            elif tool == "router_restart_wifi":
                parts.append(a.get("message", "WiFi 重启已发送"))
        for a in failures:
            parts.append(f"{a['tool']} 执行失败：{a.get('error', '未知错误')}")
        return "。".join(parts) or "好的。"
