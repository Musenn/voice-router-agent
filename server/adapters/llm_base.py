from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """一次工具调用（function calling）：工具名 + 解析后的参数字典。"""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """LLM 的一次应答：纯文本回复 text 与零个或多个工具调用 tool_calls。

    两者可以同时存在——模型既可能直接回话，也可能要求调用工具。
    """

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient(ABC):
    """大模型（LLM）适配器基类：输入对话消息，输出文本与/或工具调用。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        ...
