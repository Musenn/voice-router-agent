from abc import ABC, abstractmethod


class RouterController(ABC):
    """路由器控制适配器基类：重启路由器 / 重启 WiFi / 健康探测。"""

    @abstractmethod
    async def reboot(self) -> str:
        """重启路由器，返回一句可读的状态文本。"""
        ...

    @abstractmethod
    async def restart_wifi(self) -> str:
        """仅重启 WiFi 射频，不整机重启。"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """轻量探活：路由器有响应则返回 True。"""
        ...
