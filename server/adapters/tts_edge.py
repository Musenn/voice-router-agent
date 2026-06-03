import edge_tts
from loguru import logger

from server.adapters.tts_base import TTSClient
from server.config import settings


class EdgeTTS(TTSClient):
    """Microsoft Edge online TTS. Free, no key, decent Mandarin voices."""

    def __init__(self) -> None:
        self._voice = settings.edge_tts_voice

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""
        comm = edge_tts.Communicate(text=text, voice=self._voice)
        chunks: list[bytes] = []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        audio = b"".join(chunks)
        logger.debug("TTS produced {} bytes for {!r}", len(audio), text[:40])
        return audio
