"""Application logging configuration."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path


def configure_logger(
    name: str,
    log_file: Path,
    level: str = "INFO",
    max_bytes: int = 5_000_000,
    backup_count: int = 5,
) -> logging.Logger:
    """Create an idempotent rotating-file application logger."""
    logger = logging.getLogger(name)
    numeric_level = logging.getLevelNamesMapping().get(level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"Unknown log level: {level}")

    logger.setLevel(numeric_level)
    logger.propagate = False
    log_file = Path(log_file).resolve()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    marker = str(log_file)
    if not any(getattr(handler, "_collector_file", None) == marker for handler in logger.handlers):
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler._collector_file = marker  # type: ignore[attr-defined]
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


class _ContextFilter(logging.Filter):
    """Supply structured fields even when a caller omits them."""

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self._run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = getattr(record, "run_id", self._run_id)
        record.url = getattr(record, "url", "-")
        record.condition_id = getattr(record, "condition_id", "-")
        record.processing_status = getattr(record, "processing_status", "-")
        return True


def configure_application_logger(
    log_directory: Path, run_id: str, level: str = "INFO"
) -> logging.Logger:
    """Create daily file and console logging with structured run context."""
    numeric_level = logging.getLevelNamesMapping().get(level.upper())
    if not isinstance(numeric_level, int):
        raise ValueError(f"Unknown log level: {level}")
    directory = Path(log_directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"app_{datetime.now(UTC):%Y%m%d}.log"
    logger = logging.getLogger("hp_company_collector.application")
    logger.handlers.clear()
    logger.setLevel(numeric_level)
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s run_id=%(run_id)s url=%(url)s "
        "condition_id=%(condition_id)s status=%(processing_status)s %(message)s"
    )
    context = _ContextFilter(run_id)
    file_handler = TimedRotatingFileHandler(
        path, when="midnight", backupCount=14, encoding="utf-8", utc=True
    )
    console = logging.StreamHandler()
    for handler in (file_handler, console):
        handler.addFilter(context)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
