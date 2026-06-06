import asyncio
import platform
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from loguru import logger

from server.config import settings


@dataclass
class HealthSnapshot:
    """网络健康快照，用于对外暴露当前状态。"""

    online: bool                 # 当前是否在线（最近一次探测成功）
    consecutive_failures: int    # 连续失败次数
    last_target_ok: str | None   # 最近一次探测成功的目标地址
    in_recovery: bool            # 是否正处于自愈（恢复）流程中


class NetworkMonitor:
    """网络监控（自愈守护）：按固定间隔 ping 几个公网主机。

    连续失败达到阈值 N 次后调用 `on_outage`，让编排器去询问用户是否重启路由器；
    网络恢复后调用 `on_recovery`。
    """

    def __init__(
        self,
        on_outage: Callable[[HealthSnapshot], Awaitable[None]] | None = None,
        on_recovery: Callable[[HealthSnapshot], Awaitable[None]] | None = None,
    ) -> None:
        self._on_outage = on_outage          # 断网回调
        self._on_recovery = on_recovery      # 恢复回调
        self._task: asyncio.Task | None = None  # 后台轮询任务
        self._stop = asyncio.Event()         # 停止信号
        self._failures = 0                   # 当前连续失败计数
        self._last_ok_target: str | None = None
        self._in_recovery = False            # 是否正在自愈
        self._notified_outage = False        # 本次断网是否已通知过（避免重复触发回调）

    @property
    def snapshot(self) -> HealthSnapshot:
        return HealthSnapshot(
            online=self._failures == 0,
            consecutive_failures=self._failures,
            last_target_ok=self._last_ok_target,
            in_recovery=self._in_recovery,
        )

    def mark_recovery_started(self) -> None:
        # 标记进入自愈流程：期间不再重复触发断网回调
        self._in_recovery = True

    def mark_recovery_finished(self) -> None:
        # 自愈结束：复位各计数，回到正常监控
        self._in_recovery = False
        self._notified_outage = False
        self._failures = 0

    async def start(self) -> None:
        # 启动后台轮询任务（幂等：已在运行则不重复启动）
        if self._task is None:
            self._stop.clear()
            self._task = asyncio.create_task(self._loop(), name="network-monitor")

    async def stop(self) -> None:
        # 置停止信号并取消任务，吞掉取消/退出异常
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _loop(self) -> None:
        # 探测间隔至少 5 秒，避免配置过小把自己 ping 爆
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
                # 有任一目标可达即视为在线
                self._last_ok_target = ok_target
                # 若此前已判定为断网，现在恢复了，触发恢复回调
                if self._failures >= threshold and self._on_recovery:
                    await self._on_recovery(self.snapshot)
                self._failures = 0
                self._notified_outage = False
            else:
                # 所有目标都不可达，累加失败计数
                self._failures += 1
                logger.warning("Ping failed; consecutive failures = {}", self._failures)
                # 达到阈值、且本次断网尚未通知、且不在自愈中 → 触发断网回调（只触发一次）
                if (
                    self._failures >= threshold
                    and not self._notified_outage
                    and not self._in_recovery
                    and self._on_outage
                ):
                    self._notified_outage = True
                    await self._on_outage(self.snapshot)
            # 等待一个间隔；期间若收到停止信号则立即退出循环
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _first_reachable(self, targets: list[str]) -> str | None:
        # 依次探测，返回第一个能 ping 通的目标；全不通返回 None
        for target in targets:
            if await self._ping_once(target):
                return target
        return None

    async def _ping_once(self, target: str) -> bool:
        # 按操作系统拼 ping 命令：Windows 用 -n/-w(毫秒)，类 Unix 用 -c/-W(秒)
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
            return rc == 0  # 退出码 0 表示 ping 通
        except (asyncio.TimeoutError, FileNotFoundError, OSError):
            # 超时 / 找不到 ping 命令 / 系统错误一律视为不可达
            return False
