import json
import time

import httpx
from loguru import logger

from server.adapters.asr_base import ASRClient
from server.config import settings


_TOKEN_URL = "https://nls-meta.cn-shanghai.aliyuncs.com/"
_SHORT_ASR_URL = "https://nls-gateway-cn-shanghai.aliyuncs.com/stream/v1/asr"


class AliyunShortASR(ASRClient):
    """Aliyun NLS short-sentence recognition (一句话识别).

    Two-step flow:
      1. Exchange access key / secret for a temporary token (~24h validity).
      2. POST raw audio to the stream/v1/asr endpoint with the token.

    The official aliyunsdkcore signature is non-trivial; we cache the token
    and re-fetch when it expires. If you swap regions, update the endpoints
    above to match.
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._appkey = settings.aliyun_nls_appkey

    async def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.request import CommonRequest

        client = AcsClient(
            settings.aliyun_ak_id,
            settings.aliyun_ak_secret,
            settings.aliyun_nls_region,
        )
        req = CommonRequest()
        req.set_method("POST")
        req.set_domain(f"nls-meta.{settings.aliyun_nls_region}.aliyuncs.com")
        req.set_version("2019-02-28")
        req.set_action_name("CreateToken")

        resp = client.do_action_with_exception(req)
        payload = json.loads(resp)
        token_block = payload.get("Token") or {}
        token = token_block.get("Id")
        expire_at = token_block.get("ExpireTime")
        if not token:
            raise RuntimeError(f"Aliyun token response missing Id: {payload}")

        self._token = token
        self._token_expiry = float(expire_at) if expire_at else time.time() + 3600
        logger.debug("Refreshed Aliyun NLS token, expires at {}", self._token_expiry)
        return token

    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        token = await self._get_token()
        params = {
            "appkey": self._appkey,
            "format": "pcm",
            "sample_rate": sample_rate,
            "enable_punctuation_prediction": "true",
            "enable_inverse_text_normalization": "true",
        }
        headers = {
            "X-NLS-Token": token,
            "Content-Type": "application/octet-stream",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _SHORT_ASR_URL,
                params=params,
                content=audio_bytes,
                headers=headers,
            )
            resp.raise_for_status()
            body = resp.json()

        if body.get("status") != 20000000:
            raise RuntimeError(f"Aliyun ASR failed: {body}")
        result = body.get("result", "").strip()
        logger.info("ASR result: {!r}", result)
        return result
