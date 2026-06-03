import asyncio
import platform
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from loguru import logger

from server.config import settings


@dataclass
class HealthSnapshot:
    online: bool
    consecutive_failures: int
    last_target_ok: str | None
    in_recovery: bool


class NetworkMonitor:
    """Pings a few public hosts on a schedule. After N consecutive failures
    the monitor calls `on_outage` so the orchestrator can ask the user
    whether to reboot the router. After recovery it calls `on_recovery`."""

    def __init__(
        self,
        on_outage: Callable[[HealthSnapshot], Awaitable[None]] | None = None,
        on_recovery: Callable[[HealthSnapshot], Awaitable[None]] | None = None,
    ) -> None:
        self._on_outage = on_outage
        self._on_recovery = on_recovery
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._failures = 0
        self._last_ok_target: str | None = None
        self._in_recovery = False
        self._notified_outage = False

    @property
    def snapshot(self) -> HealthSnapshot:
        return HealthSnapshot(
            online=self._failures == 0,
            consecutive_failures=self._failures,
            last_target_ok=self._last_ok_target,
            in_recovery=self._in_recovery,
        )

    def mark_recovery_started(self) -> None:
        self._in_recovery = True

    def mark_recovery_finished(self) -> None:
        self._in_recovery = False
        self._notified_outage = False
        self._failures = 0

    async def start(self) -> None:
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._loop(), name="network-monitor")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _loop(self) -> None:
        interval = max(5, settings.selfheal_interval_seconds)
        targets = settings.ping_targets
        threshold = settings.selfheal_failure_threshold
        if not targets:
            logger.warning("Self-heal disabled: no ping targets configured")
            return

        logger.info("Network monitor watching {} every {}s", targets, interval)
        while not self._stop.is_set():
            ok_target = await self._first_reachable(targets)
            if ok_target:
                self._last_ok_target = ok_target
                if self._failures >= threshold and self._on_recovery:
                    await self._on_recovery(self.snapshot)
                self._failures = 0
                self._notified_outage = False
            else:
                self._failures += 1
                logger.warning("Ping failed; consecutive failures = {}", self._failures)
                if (
                    self._failures >= threshold
                    and not self._notified_outage
                    and not self._in_recovery
                    and self._on_outage
                ):
                    self._notified_outage = True
                    await self._on_outage(self.snapshot)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _first_reachable(self, targets: list[str]) -> str | None:
        for target in targets:
            if await self._ping_once(target):
                return target
        return None

    async def _ping_once(self, target: str) -> bool:
        if platform.system().lower().startswith("win"):
            cmd = ["ping", "-n", "1", "-w", "1500", target]
        else:
            cmd = ["ping", "-c", "1", "-W", "2", target]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            rc = await asyncio.wait_for(proc.wait(), timeout=5)
            return rc == 0
        except (asyncio.TimeoutError, FileNotFoundError, OSError):
            return False
