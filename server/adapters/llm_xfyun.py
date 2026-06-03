import json
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from server.adapters.llm_base import LLMClient, LLMResponse, ToolCall
from server.config import settings


class XfyunMaaSLLM(LLMClient):
    """iFlytek MaaS exposes an OpenAI-compatible chat completions API.

    Auth is the access key and secret joined with a colon, passed as the
    bearer token. If the provider rejects this format, switch to the HMAC
    signature flow documented in the MaaS console.
    """

    def __init__(self) -> None:
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
        extra_body: dict[str, Any] = {}
        if settings.xfyun_resource_id:
            extra_body["resource_id"] = settings.xfyun_resource_id

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "extra_body": extra_body,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        completion = await self._client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        msg = choice.message

        calls: list[ToolCall] = []
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except json.JSONDecodeError:
                logger.warning("Tool call arguments not JSON: {}", tc.function.arguments)
                args = {}
            calls.append(ToolCall(name=tc.function.name, arguments=args))

        return LLMResponse(text=msg.content or "", tool_calls=calls)
