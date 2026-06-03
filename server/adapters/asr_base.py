from abc import ABC, abstractmethod


class ASRClient(ABC):
    """Convert a PCM/WAV audio blob into a single utterance string."""

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, sample_rate: int = 16000) -> str:
        ...
