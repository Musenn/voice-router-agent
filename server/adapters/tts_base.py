from abc import ABC, abstractmethod


class TTSClient(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Return MP3 audio bytes for the given text."""
        ...
