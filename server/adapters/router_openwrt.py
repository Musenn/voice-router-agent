import asyncio

import paramiko
from loguru import logger

from server.adapters.router_base import RouterController
from server.config import settings


class OpenWRTRouter(RouterController):
    """通过 SSH 在 OpenWrt 路由器上执行 shell 命令。

    重启是「发出即不管」的：路由器一重启，SSH 连接随之断开，因此把由此产生的
    异常当作预期情况捕获，而不是判定为失败。
    """

    def _connect(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        # 家庭环境自动接受未知主机密钥；如需更严格可改用 known_hosts 策略
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: dict = {
            "hostname": settings.router_host,
            "port": settings.router_port,
            "username": settings.router_user,
            "timeout": 10,
        }
        # 优先用私钥认证，其次用密码；两者都没配则直接报错
        if settings.router_key_path:
            kwargs["key_filename"] = settings.router_key_path
        elif settings.router_password:
            kwargs["password"] = settings.router_password
        else:
            raise RuntimeError("Router SSH needs either ROUTER_KEY_PATH or ROUTER_PASSWORD")
        client.connect(**kwargs)
        return client

    async def _run(self, cmd: str, ignore_drop: bool = False) -> str:
        # paramiko 是同步阻塞库，放到线程池里跑，避免阻塞事件循环。
        # ignore_drop=True 时，把连接断开当作预期结果（用于 reboot）
        def _sync() -> str:
            try:
                client = self._connect()
            except Exception as e:
                if ignore_drop:
                    return f"(connection drop expected) {e!r}"
                raise
            try:
                stdin, stdout, stderr = client.exec_command(cmd, timeout=15)
                out = stdout.read().decode("utf-8", errors="replace")
                err = stderr.read().decode("utf-8", errors="replace")
                if err.strip():
                    logger.warning("router stderr: {}", err.strip())
                return out.strip() or err.strip()
            except Exception as e:
                if ignore_drop:
                    return f"(connection drop expected) {e!r}"
                raise
            finally:
                client.close()

        return await asyncio.get_running_loop().run_in_executor(None, _sync)

    async def reboot(self) -> str:
        logger.warning("Rebooting router via SSH")
        # 整机重启，连接会断开，故 ignore_drop=True
        out = await self._run("reboot", ignore_drop=True)
        return f"路由器已收到重启指令：{out or 'ok'}"

    async def restart_wifi(self) -> str:
        # 仅重载 WiFi，不断 SSH 连接
        out = await self._run("wifi reload")
        return f"WiFi 已重启：{out or 'ok'}"

    async def health_check(self) -> bool:
        # 跑一条 echo 探活：能拿到回显 ok 即认为路由器在线
        try:
            out = await self._run("echo ok")
            return out.strip().endswith("ok")
        except Exception as e:
            logger.debug("router health_check failed: {}", e)
            return False
