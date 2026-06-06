from abc import ABC, abstractmethod


class ASRClient(ABC):
    """语音识别（ASR）适配器基类：把一段 PCM/WAV 音频数据转写成一句话文本。"""

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        # audio_bytes：原始 16 位小端单声道 PCM 字节流；返回识别出的文本
        ...
