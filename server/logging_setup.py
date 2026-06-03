import sys
from pathlib import Path

from loguru import logger

from server.config import PROJECT_ROOT, settings


def configure_logging() -> None:
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format="<green>{time:HH:mm:ss}</green> <level>{level: <7}</level> "
               "<cyan>{name}:{line}</cyan> {message}",
    )
    logger.add(
        log_dir / "server.log",
        level="DEBUG",
        rotation="5 MB",
        retention=5,
        encoding="utf-8",
    )
