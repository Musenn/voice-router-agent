import json
import re
from typing import Any

from loguru import logger

from server.adapters.llm_base import LLMClient, LLMResponse, ToolCall


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
    """Pattern-matches on user text. Lets you exercise the whole pipeline
    without an LLM provider configured."""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        last_user = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        text = last_user if isinstance(last_user, str) else json.dumps(last_user)
        logger.debug("MockLLM input: {!r}", text)

        for pattern, tool_name, args in _RULES:
            if pattern.search(text):
                return LLMResponse(tool_calls=[ToolCall(name=tool_name, arguments=args)])

        return LLMResponse(text="我没听懂这个指令，可以换种说法吗？")
