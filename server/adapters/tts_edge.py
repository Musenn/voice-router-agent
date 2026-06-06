import edge_tts
from loguru import logger

from server.adapters.tts_base import TTSClient
from server.config import settings


class EdgeTTS(TTSClient):
    """微软 Edge 在线语音合成：免费、无需密钥，中文音色质量不错。"""

    def __init__(self) -> None:
        self._voice = settings.edge_tts_voice  # 音色，如 zh-CN-XiaoxiaoNeural（晓晓）

    async def synthesize(self, text: str) -> bytes:
        if not text.strip():
            return b""  # 空文本直接返回空音频，省去一次网络往返
        comm = edge_tts.Communicate(text=text, voice=self._voice)
        # 流式接收，逐块拼接出完整 MP3；只取 audio 类型分片（其余是字幕等元信息）
        chunks: list[bytes] = []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        audio = b"".join(chunks)
        logger.debug("TTS produced {} bytes for {!r}", len(audio), text[:40])
        return audio
