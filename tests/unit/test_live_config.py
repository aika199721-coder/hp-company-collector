"""Separated live-validation safety configuration tests."""

from pathlib import Path

import pytest

from live.config import LiveValidationConfig

ROOT = Path(__file__).resolve().parents[2]


def test_live_configuration_enforces_initial_ceilings() -> None:
    config = LiveValidationConfig.load(ROOT / "config/live_validation.yaml")
    assert config.max_conditions == 1
    assert config.max_business_targets == 3
    assert config.max_candidates == 20
    assert config.delay_seconds >= 5


def test_unsafe_live_configuration_is_rejected(tmp_path: Path) -> None:
    text = (ROOT / "config/live_validation.yaml").read_text(encoding="utf-8")
    path = tmp_path / "live.yaml"
    path.write_text(text.replace("max_candidates: 20", "max_candidates: 21"), encoding="utf-8")
    with pytest.raises(ValueError, match="ceiling"):
        LiveValidationConfig.load(path)
