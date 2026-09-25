"""
Centralised logging factory for the project.

Usage in every module:
    from src.logger import get_logger
    logger = get_logger(__name__)

Call apply_log_level(config.logging.level) once after config loads.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_LOG_DIR = Path(__file__).parent.parent / "logs"
_DEFAULT_LEVEL = "INFO"
_DEFAULT_MAX_BYTES = 100 * 1024  # 100 KB
_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%dT%H:%M:%S"

_handler_attached = False


def _attach_handlers(
    log_dir: Path,
    max_bytes: int,
    level: int,
) -> None:
    """Attach file handler to the root logger (once only)."""
    global _handler_attached
    if _handler_attached:
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "agent.log"

    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _handler_attached = True


def get_logger(
    name: str,
    log_dir: Optional[Path] = None,
    max_size_kb: int = 100,
) -> logging.Logger:
    """Return a named logger, attaching handlers on first call."""
    _attach_handlers(
        log_dir=log_dir or _LOG_DIR,
        max_bytes=max_size_kb * 1024,
        level=logging.getLevelName(_DEFAULT_LEVEL),
    )
    return logging.getLogger(name)


def apply_log_level(level: str) -> None:
    """Update the root logger and all its handlers to the given level string."""
    numeric = logging.getLevelName(level.upper())
    root = logging.getLogger()
    root.setLevel(numeric)
    for handler in root.handlers:
        handler.setLevel(numeric)
