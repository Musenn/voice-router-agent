from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from server.adapters import DeviceController, LLMClient, RouterController, ToolCall
from server.intent.tools import SYSTEM_PROMPT, TOOLS


@dataclass
class TurnResult:
    transcript: str
    reply_text: str
    actions: list[dict[str, Any]] = field(default_factory=list)


class IntentOrchestrator:
    """One-shot orchestration: take user text, ask LLM, run any tool calls,
    collect a final reply. No multi-turn memory for now — every request is
    standalone."""

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
        if not user_text.strip():
            return TurnResult(transcript="", reply_text="我没听清，请再说一遍。")

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]

        response = await self._llm.chat(messages, tools=TOOLS)
        actions: list[dict[str, Any]] = []

        if response.tool_calls:
            for call in response.tool_calls:
                outcome = await self._dispatch(call)
                actions.append(outcome)
            reply = self._format_reply(actions, response.text)
        else:
            reply = response.text or "好的。"

        return TurnResult(transcript=user_text, reply_text=reply, actions=actions)

    async def _dispatch(self, call: ToolCall) -> dict[str, Any]:
        logger.info("dispatch tool={} args={}", call.name, call.arguments)
        try:
            if call.name == "set_device_state":
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
            logger.exception("tool {} failed", call.name)
            return {"tool": call.name, "ok": False, "error": str(e)}

    def _format_reply(self, actions: list[dict[str, Any]], llm_text: str) -> str:
        if llm_text.strip():
            return llm_text.strip()

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
