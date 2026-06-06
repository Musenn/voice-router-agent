from loguru import logger

from server.adapters.asr_base import ASRClient


class MockASR(ASRClient):
    """模拟 ASR：无论输入什么音频都返回一句固定文本。

    用于在没有真实云端账号的情况下跑通后续整条管线（LLM → 工具调用 → TTS）。
    """

    def __init__(self, canned: str = "打开客厅的灯") -> None:
        self.canned = canned  # 预置的固定识别结果

    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        logger.debug("MockASR received {} bytes @ {}Hz", len(audio_bytes), sample_rate)
        return self.canned
