"""Build and validate the self-contained Windows distribution ZIP."""

from __future__ import annotations

import hashlib
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="ascii").strip()
ARCHIVE_ROOT = "hp_company_collector"
INCLUDE_FILES = (
    "README.md",
    "requirements.txt",
    "VERSION",
    "setup.bat",
    "validate.bat",
    "collect.bat",
    "resume.bat",
    "status.bat",
    "export.bat",
    "reset_retries.bat",
    "diagnostics.bat",
    "live_check.bat",
    "review_import.bat",
    "live_report.bat",
    "docs/windows_setup.md",
    "docs/live_validation.md",
    "input/search_conditions_sample.csv",
)
INCLUDE_TREES = ("src", "scripts/windows")
CONFIG_FILES = (
    "default.yaml",
    "providers.yaml",
    "pipeline.yaml",
    "scoring.yaml",
    "industry_keywords.yaml",
    "exclude_domains.txt",
    "live_validation.yaml",
)
EMPTY_DIRS = ("data", "logs", "output")
FORBIDDEN_PARTS = {".git", ".github", ".venv", "__pycache__", ".pytest_cache", "tests"}
SETUPFIX_MARKER = b"setupfix11.2.2.1-v1"
CANONICAL_LAUNCHERS = (
    "setup.bat",
    "validate.bat",
    "live_check.bat",
    "scripts/windows/setup.ps1",
    "scripts/windows/common.ps1",
    "scripts/windows/validate.ps1",
    "scripts/windows/live_check.ps1",
)


def build_release(destination: Path | None = None) -> Path:
    """Create a deterministic-root ZIP and validate its safe contents."""
    output = destination or ROOT / "dist" / f"hp_company_collector_v{VERSION}_windows.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in INCLUDE_FILES:
            _write(archive, relative)
        for name in CONFIG_FILES:
            _write(archive, f"config/{name}")
        for tree in INCLUDE_TREES:
            for path in sorted((ROOT / tree).rglob("*")):
                if path.is_file() and not FORBIDDEN_PARTS.intersection(path.parts):
                    _write(archive, path.relative_to(ROOT).as_posix())
        for directory in EMPTY_DIRS:
            archive.writestr(f"{ARCHIVE_ROOT}/{directory}/.gitkeep", "")
    validate_release(output)
    return output


def validate_release(archive_path: Path) -> None:
    """Verify required files, exclusions, version consistency, and extraction."""
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        required = {f"{ARCHIVE_ROOT}/{name}" for name in INCLUDE_FILES}
        required.add(f"{ARCHIVE_ROOT}/config/default.yaml")
        missing = required - names
        if missing:
            raise ValueError(f"release files missing: {sorted(missing)}")
        for name in names:
            parts = Path(name).parts
            if FORBIDDEN_PARTS.intersection(parts) or name.endswith("config/local.yaml"):
                raise ValueError(f"forbidden release entry: {name}")
            if name.endswith("input/search_conditions.csv"):
                raise ValueError("actual search conditions must not be distributed")
        if archive.read(f"{ARCHIVE_ROOT}/VERSION").decode("ascii").strip() != VERSION:
            raise ValueError("release version mismatch")
        _validate_source_hashes(archive)
        for relative in CANONICAL_LAUNCHERS:
            _validate_setup_source(archive, relative)
        for name in names:
            if name.endswith(".ps1"):
                _validate_powershell_encoding(archive.read(name), name)
        with tempfile.TemporaryDirectory(prefix="配布 検査 (Phase10) ") as temporary:
            archive.extractall(temporary)
            extracted = Path(temporary) / ARCHIVE_ROOT
            if not (extracted / "setup.bat").is_file():
                raise ValueError("extracted setup.bat is missing")
            source = (extracted / "src/__version__.py").read_text(encoding="utf-8")
            if "VERSION" not in source:
                raise ValueError("application version is not sourced from VERSION")


def _write(archive: zipfile.ZipFile, relative: str) -> None:
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    archive.write(path, f"{ARCHIVE_ROOT}/{relative}")


def _validate_setup_source(archive: zipfile.ZipFile, relative: str) -> None:
    """Require the canonical marker and reject obsolete batch invocation logic."""
    source = (ROOT / relative).read_bytes()
    packaged = archive.read(f"{ARCHIVE_ROOT}/{relative}")
    if SETUPFIX_MARKER not in source or SETUPFIX_MARKER not in packaged:
        raise ValueError(f"setupfix11.2.2.1 marker missing: {relative}")
    if hashlib.sha256(source).digest() != hashlib.sha256(packaged).digest():
        raise ValueError(f"stale setup file in release: {relative}")
    lowered = packaged.lower()
    if b"cmdcmdline" in lowered or b"^&" in packaged:
        raise ValueError(f"obsolete launcher logic in release: {relative}")


def _validate_source_hashes(archive: zipfile.ZipFile) -> None:
    """Require every distributed BAT, PowerShell, and Python file to match source."""
    for name in archive.namelist():
        if not name.endswith((".bat", ".ps1", ".py")):
            continue
        relative = name.removeprefix(f"{ARCHIVE_ROOT}/")
        source = ROOT / relative
        if not source.is_file():
            raise ValueError(f"release source missing: {relative}")
        if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(
            archive.read(name)
        ).digest():
            raise ValueError(f"release hash mismatch: {relative}")


def _validate_powershell_encoding(content: bytes, name: str) -> None:
    """Enforce Windows PowerShell 5.1-safe UTF-8 BOM and CRLF line endings."""
    if not content.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"PowerShell UTF-8 BOM missing: {name}")
    body = content[3:]
    if b"\n" in body.replace(b"\r\n", b""):
        raise ValueError(f"PowerShell contains non-CRLF line endings: {name}")


if __name__ == "__main__":
    print(build_release())
