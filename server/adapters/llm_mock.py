import json
import re
from typing import Any

from loguru import logger

from server.adapters.llm_base import LLMClient, LLMResponse, ToolCall


# 规则表：(正则, 命中后调用的工具名, 工具参数)。按顺序匹配，命中第一条即返回。
_RULES: list[tuple[re.Pattern[str], str, dict[str, Any]]] = [
    (re.compile(r"打开|开启|开.*灯"), "set_device_state",
     {"device_id": "light_livingroom", "state": "on"}),
    (re.compile(r"关闭|关.*灯|关掉"), "set_device_state",
     {"device_id": "light_livingroom", "state": "off"}),
    (re.compile(r"温度|调到|空调"), "set_device_state",
     {"device_id": "ac_livingroom", "state": "on", "temperature": 24}),
    (re.compile(r"重启.*路由|路由.*重启|网.*不上|没有.*网"), "router_reboot", {}),
    (re.compile(r"状态|有什么设备"), "list_devices", {}),
]


class MockLLM(LLMClient):
    """模拟 LLM：用正则匹配用户文本来挑选工具。

    在未配置真实大模型时，可以用它跑通整条管线（无需任何云端账号）。
    """

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        # 取最近一条用户消息作为匹配输入
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        text = last_user if isinstance(last_user, str) else json.dumps(last_user)
        logger.debug("MockLLM input: {!r}", text)

        # 命中任一规则即返回对应工具调用
        for pattern, tool_name, args in _RULES:
            if pattern.search(text):
                return LLMResponse(tool_calls=[ToolCall(name=tool_name, arguments=args)])

        # 全部未命中：返回一句兜底文本，不触发任何工具
        return LLMResponse(text="我没听懂这个指令，可以换种说法吗？")
