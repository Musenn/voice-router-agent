from abc import ABC, abstractmethod
from typing import Any


class DeviceController(ABC):
    @abstractmethod
    def list_devices(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_device(self, device_id: str) -> dict[str, Any] | None:
        ...

    @abstractmethod
    def set_state(self, device_id: str, **kwargs: Any) -> dict[str, Any]:
        """Apply the given fields to the device and return the new snapshot."""
        ...
