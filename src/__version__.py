"""Application version loaded from the single distribution source."""

from pathlib import Path


def _read_version() -> str:
    """Read the repository VERSION file."""
    return (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="ascii").strip()


__version__ = _read_version()
