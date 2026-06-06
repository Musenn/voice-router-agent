import json
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from server.adapters.llm_base import LLMClient, LLMResponse, ToolCall
from server.config import settings


class XfyunMaaSLLM(LLMClient):
    """讯飞 MaaS 大模型适配器：其对外提供与 OpenAI 兼容的 chat completions 接口。

    鉴权方式是把 API Key 和 Secret 用冒号拼接后作为 Bearer Token 传入。
    若该格式被服务端拒绝，请改用 MaaS 控制台文档里的 HMAC 签名流程。
    """

    def __init__(self) -> None:
        # 把「key:secret」整体作为 Bearer Token；直接复用 OpenAI SDK 发请求
        token = f"{settings.xfyun_api_key}:{settings.xfyun_api_secret}"
        self._client = AsyncOpenAI(
            api_key=token,
            base_url=settings.xfyun_base_url,
            timeout=60.0,
        )
        self._model = settings.xfyun_model_id

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        # 讯飞特有的 resource_id 通过 extra_body 透传给底层接口
        extra_body: dict[str, Any] = {}
        if settings.xfyun_resource_id:
            extra_body["resource_id"] = settings.xfyun_resource_id

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,          # 低温度，让指令解析更稳定、少发散
            "extra_body": extra_body,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"  # 由模型自行决定是否调用工具

        completion = await self._client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        msg = choice.message

        # 把 OpenAI 格式的 tool_calls 转换成本项目内部的 ToolCall
        calls: list[ToolCall] = []
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                # 参数不是合法 JSON 时记录告警并退化为空参数，避免整个请求崩溃
                logger.warning("Tool call arguments not JSON: {}", tc.function.arguments)
                args = {}
            calls.append(ToolCall(name=tc.function.name, arguments=args))

        return LLMResponse(text=msg.content or "", tool_calls=calls)
