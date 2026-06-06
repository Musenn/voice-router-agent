import json
import time

import httpx
from loguru import logger

from server.adapters.asr_base import ASRClient
from server.config import settings


_TOKEN_URL = "https://nls-meta.cn-shanghai.aliyuncs.com/"
_SHORT_ASR_URL = "https://nls-gateway-cn-shanghai.aliyuncs.com/stream/v1/asr"


class AliyunShortASR(ASRClient):
    """阿里云智能语音交互（NLS）「一句话识别」适配器。

    调用分两步：
      1. 用 AccessKey ID / Secret 换取一个临时 Token（有效期约 24 小时）。
      2. 带上 Token，把原始音频 POST 到 stream/v1/asr 接口。

    官方 aliyunsdkcore 的签名流程较繁琐，这里把 Token 缓存起来，过期后再重新获取。
    如果切换地域（region），需要同步修改上方的接口地址常量。
    """

    def __init__(self) -> None:
        self._token: str | None = None          # 缓存的 Token
        self._token_expiry: float = 0.0          # Token 过期时间（Unix 时间戳）
        self._appkey = settings.aliyun_nls_appkey

    async def _get_token(self) -> str:
        # Token 未过期（留 60 秒余量）则直接复用缓存，避免每次识别都重新签发
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
        # 接口未返回过期时间时，保守地按 1 小时后过期处理
        self._token_expiry = float(expire_at) if expire_at else time.time() + 3600
        logger.debug("Refreshed Aliyun NLS token, expires at {}", self._token_expiry)
        return token

    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        token = await self._get_token()
        params = {
            "appkey": self._appkey,
            "format": "pcm",                              # 上传的是原始 PCM
            "sample_rate": sample_rate,
            "enable_punctuation_prediction": "true",      # 开启标点预测
            # 开启 ITN 数字规范化（如「一百」→「100」）
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

        # 20000000 是阿里云 NLS 约定的「成功」状态码，其余一律视为失败
        if body.get("status") != 20000000:
            raise RuntimeError(f"Aliyun ASR failed: {body}")
        result = body.get("result", "").strip()
        logger.info("ASR result: {!r}", result)
        return result
