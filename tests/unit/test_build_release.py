"""Offline Windows distribution archive tests."""

import hashlib
import zipfile
from pathlib import Path

from scripts.build_release import ARCHIVE_ROOT, build_release


def test_release_contains_required_files_and_excludes_runtime_data(tmp_path: Path) -> None:
    output = build_release(tmp_path / "release.zip")

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    assert f"{ARCHIVE_ROOT}/setup.bat" in names
    assert f"{ARCHIVE_ROOT}/input/search_conditions_sample.csv" in names
    assert not any("tests/" in name for name in names)
    assert not any(name.endswith("search_conditions.csv") for name in names)
    assert not any(name.endswith("config/local.yaml") for name in names)


def test_ci_uploads_exact_release_filename() -> None:
    """Keep generated binary archives out of Git and upload the exact CI artifact path."""
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    ignore = (root / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "dist/" in ignore
    assert "uses: actions/upload-artifact@v4" in workflow
    assert "path: dist/hp_company_collector_v0.10.0_windows.zip" in workflow
    assert "SOURCE_SHA: ${{ github.event.pull_request.head.sha || github.sha }}" in workflow
    assert "ref: ${{ env.SOURCE_SHA }}" in workflow
    assert "Verify packaged setupfix8 content and SHA256" in workflow
    assert "hp_company_collector_v0.10.0_windows-${{" in workflow


def test_release_setup_files_exactly_match_current_checkout(tmp_path: Path) -> None:
    """Reject stale setup files even when a ZIP otherwise has valid structure."""
    root = Path(__file__).resolve().parents[2]
    output = build_release(tmp_path / "release.zip")

    with zipfile.ZipFile(output) as archive:
        batch = archive.read(f"{ARCHIVE_ROOT}/setup.bat")
        powershell = archive.read(f"{ARCHIVE_ROOT}/scripts/windows/setup.ps1")
    assert hashlib.sha256(batch).digest() == hashlib.sha256(
        (root / "setup.bat").read_bytes()
    ).digest()
    assert hashlib.sha256(powershell).digest() == hashlib.sha256(
        (root / "scripts/windows/setup.ps1").read_bytes()
    ).digest()
