from abc import ABC, abstractmethod


class RouterController(ABC):
    @abstractmethod
    async def reboot(self) -> str:
        """Reboot the router. Returns a short human-readable status string."""
        ...

    @abstractmethod
    async def restart_wifi(self) -> str:
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Lightweight probe; True if the router responds."""
        ...
