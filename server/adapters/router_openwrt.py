import asyncio

import paramiko
from loguru import logger

from server.adapters.router_base import RouterController
from server.config import settings


class OpenWRTRouter(RouterController):
    """Run shell commands on an OpenWrt router via SSH.

    Reboot is fire-and-forget: the SSH connection drops with the box, so we
    catch the resulting error rather than treating it as a failure.
    """

    def _connect(self) -> paramiko.SSHClient:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kwargs: dict = {
            "hostname": settings.router_host,
            "port": settings.router_port,
            "username": settings.router_user,
            "timeout": 10,
        }
        if settings.router_key_path:
            kwargs["key_filename"] = settings.router_key_path
        elif settings.router_password:
            kwargs["password"] = settings.router_password
        else:
            raise RuntimeError("Router SSH needs either ROUTER_KEY_PATH or ROUTER_PASSWORD")
        client.connect(**kwargs)
        return client

    async def _run(self, cmd: str, ignore_drop: bool = False) -> str:
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
        out = await self._run("reboot", ignore_drop=True)
        return f"路由器已收到重启指令：{out or 'ok'}"

    async def restart_wifi(self) -> str:
        out = await self._run("wifi reload")
        return f"WiFi 已重启：{out or 'ok'}"

    async def health_check(self) -> bool:
        try:
            out = await self._run("echo ok")
            return out.strip().endswith("ok")
        except Exception as e:
            logger.debug("router health_check failed: {}", e)
            return False
