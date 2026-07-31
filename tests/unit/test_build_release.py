"""Offline Windows distribution archive tests."""

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
