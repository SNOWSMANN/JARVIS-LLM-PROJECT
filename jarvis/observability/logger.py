"""Structured logging for Jarvis."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from jarvis.config import settings

_CONFIGURED = False


def setup_logging() -> None:
    """Configure loguru sinks. Idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logger.remove()

    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:HH:mm:ss}</green> "
            "<level>{level: <7}</level> "
            "<cyan>{name}:{function}</cyan> - "
            "<level>{message}</level>"
        ),
        enqueue=True,
    )

    log_file = Path(settings.logs_path) / "jarvis.log"
    logger.add(
        str(log_file),
        level="DEBUG",
        rotation="20 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    if settings.audit_log:
        audit_file = Path(settings.logs_path) / "audit.log"
        logger.add(
            str(audit_file),
            level="INFO",
            rotation="50 MB",
            retention="90 days",
            filter=lambda r: r["extra"].get("audit") is True,
            enqueue=True,
        )

    _CONFIGURED = True


def get_logger(name: str):
    """Get a bound logger for a module."""
    setup_logging()
    return logger.bind(module=name)
