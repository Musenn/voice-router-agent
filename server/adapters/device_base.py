from abc import ABC, abstractmethod
from typing import Any


class DeviceController(ABC):
    """智能设备控制适配器基类：列出设备 / 查询单个设备 / 修改设备状态。"""

    @abstractmethod
    def list_devices(self) -> list[dict[str, Any]]:
        """返回所有已知设备的状态列表。"""
        ...

    @abstractmethod
    def get_device(self, device_id: str) -> dict[str, Any] | None:
        """按 id 查询单个设备，不存在返回 None。"""
        ...

    @abstractmethod
    def set_state(self, device_id: str, **kwargs: Any) -> dict[str, Any]:
        """把给定字段写入设备，并返回更新后的设备快照。"""
        ...
