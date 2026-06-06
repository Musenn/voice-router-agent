from abc import ABC, abstractmethod


class TTSClient(ABC):
    """语音合成（TTS）适配器基类。"""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """把文本合成为语音，返回 MP3 音频字节。"""
        ...
