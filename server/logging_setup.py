import sys
from pathlib import Path

from loguru import logger

from server.config import PROJECT_ROOT, settings


def configure_logging() -> None:
    """配置 loguru 日志：彩色输出到终端 + 滚动写入文件。"""
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    logger.remove()  # 移除 loguru 默认 handler，避免重复输出
    # 终端输出：按 .env 的 LOG_LEVEL 过滤，带颜色
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> <level>{level: <7}</level> "
               "<cyan>{name}:{line}</cyan> {message}",
    )
    # 文件输出：固定 DEBUG 全量记录，单文件超 5MB 滚动、最多保留 5 个
    logger.add(
        log_dir / "server.log",
        level="DEBUG",
        rotation="5 MB",
        retention=5,
        encoding="utf-8",
    )
