from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | "
    "{level} | "
    "{file.name}:{line} | "
    "{message}"
)


def setup_logging(log_file: str = "logs/self-manager.log"):
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format=LOG_FORMAT,
        colorize=False,
        enqueue=False,
    )
    logger.add(
        str(log_path),
        level="INFO",
        format=LOG_FORMAT,
        encoding="utf-8",
        enqueue=False,
    )
    return logger
