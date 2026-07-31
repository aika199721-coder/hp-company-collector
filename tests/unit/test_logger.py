"""Logger configuration tests."""

import logging
from pathlib import Path

import pytest

from utils.logger import configure_logger


def test_logger_writes_utf8_and_does_not_duplicate_handlers(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "collector.log"
    logger = configure_logger("test.collector", path, "INFO")
    before = len(logger.handlers)
    same_logger = configure_logger("test.collector", path, "DEBUG")

    same_logger.info("企業ログ")
    for handler in same_logger.handlers:
        handler.flush()

    assert len(same_logger.handlers) == before
    assert "企業ログ" in path.read_text(encoding="utf-8")


def test_logger_rejects_unknown_level(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown log level"):
        configure_logger("test.invalid", tmp_path / "x.log", "LOUD")

    logging.getLogger("test.invalid").handlers.clear()
