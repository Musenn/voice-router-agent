from loguru import logger

from server.adapters.router_base import RouterController


class MockRouter(RouterController):
    """Logs the action that would have been taken. Used until a real OpenWrt
    box is wired in."""

    async def reboot(self) -> str:
        logger.warning("[mock] would SSH router and run `reboot`")
        return "已模拟重启路由器（mock 模式，未真实执行）"

    async def restart_wifi(self) -> str:
        logger.warning("[mock] would restart wifi via `/etc/init.d/network restart`")
        return "已模拟重启 WiFi（mock 模式，未真实执行）"

    async def health_check(self) -> bool:
        return True
