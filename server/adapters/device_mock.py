import time
from typing import Any

from loguru import logger

from server.adapters.device_base import DeviceController


def _now_iso() -> str:
    # 返回当前时间的 ISO 字符串，用作设备的 updated_at 时间戳
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class MockDeviceFleet(DeviceController):
    """内存中的一组虚拟家电。状态只存活于进程生命周期内，进程重启即重置——
    对一个学习项目而言足够了。要持久化时再加一层 SQLite 即可。
    """

    def __init__(self) -> None:
        self._devices: dict[str, dict[str, Any]] = {
            "light_livingroom": {
                "id": "light_livingroom",
                "name": "客厅主灯",
                "type": "light",
                "state": "off",
                "brightness": 80,
                "updated_at": _now_iso(),
            },
            "light_bedroom": {
                "id": "light_bedroom",
                "name": "卧室灯",
                "type": "light",
                "state": "off",
                "brightness": 60,
                "updated_at": _now_iso(),
            },
            "ac_livingroom": {
                "id": "ac_livingroom",
                "name": "客厅空调",
                "type": "air_conditioner",
                "state": "off",
                "temperature": 26,
                "mode": "cool",
                "updated_at": _now_iso(),
            },
            "curtain_livingroom": {
                "id": "curtain_livingroom",
                "name": "客厅窗帘",
                "type": "curtain",
                "state": "closed",
                "updated_at": _now_iso(),
            },
        }

    def list_devices(self) -> list[dict[str, Any]]:
        return list(self._devices.values())

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        return self._devices.get(device_id)

    def set_state(self, device_id: str, **kwargs: Any) -> dict[str, Any]:
        dev = self._devices.get(device_id)
        if dev is None:
            raise KeyError(f"unknown device: {device_id}")
        # 逐字段写入；值为 None 的字段跳过，避免把未提供的参数误写成空值
        for key, value in kwargs.items():
            if value is None:
                continue
            dev[key] = value
        dev["updated_at"] = _now_iso()
        logger.info("Device {} updated: {}", device_id, kwargs)
        return dev
