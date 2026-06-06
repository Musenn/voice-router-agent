from loguru import logger

from server.adapters.router_base import RouterController


class MockRouter(RouterController):
    """模拟路由器：只把「本应执行的动作」打到日志，不做任何真实操作。

    在接入真实 OpenWrt 设备之前用它占位，方便安全地走通自愈流程。
    """

    async def reboot(self) -> str:
        logger.warning("[mock] would SSH router and run `reboot`")
        return "已模拟重启路由器（mock 模式，未真实执行）"

    async def restart_wifi(self) -> str:
        logger.warning("[mock] would restart wifi via `/etc/init.d/network restart`")
        return "已模拟重启 WiFi（mock 模式，未真实执行）"

    async def health_check(self) -> bool:
        return True
