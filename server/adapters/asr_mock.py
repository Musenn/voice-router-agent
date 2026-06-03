from loguru import logger

from server.adapters.asr_base import ASRClient


class MockASR(ASRClient):
    """Returns a canned phrase. Useful for running the rest of the pipeline
    without a real cloud account."""

    def __init__(self, canned: str = "打开客厅的灯") -> None:
        self.canned = canned

    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        logger.debug("MockASR received {} bytes @ {}Hz", len(audio_bytes), sample_rate)
        return self.canned
