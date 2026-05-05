from __future__ import annotations

import sys
import os
from pathlib import Path

from loguru import logger


LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | "
    "{level} | "
    "{file.name}:{line} | "
    "{message}"
)


def setup_logging(log_file: str = "logs/self-manager.log"):
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format=LOG_FORMAT,
        colorize=False,
        enqueue=False,
    )
    if os.getenv("VERCEL"):
        return logger

    try:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_path),
            level="INFO",
            format=LOG_FORMAT,
            encoding="utf-8",
            enqueue=False,
        )
    except OSError as exc:
        logger.warning("文件日志不可用，仅输出到控制台: {}", exc)
    return logger
