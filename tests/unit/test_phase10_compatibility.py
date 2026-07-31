"""Python runtime and single-source version tests."""

from pathlib import Path

from __version__ import __version__
from application.compatibility import check_runtime

ROOT = Path(__file__).resolve().parents[2]


def test_python_313_and_architecture_checks() -> None:
    assert check_runtime((3, 13), 64).supported is True
    assert check_runtime((3, 13), 32).is_64bit is False
    assert check_runtime((3, 12), 64).supported is False


def test_version_matches_distribution_sources() -> None:
    assert __version__ == "0.10.0"
    assert (ROOT / "VERSION").read_text(encoding="ascii").strip() == __version__
    assert 'version = "0.10.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
