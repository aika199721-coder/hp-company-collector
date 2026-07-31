"""Phase 8 Step 4 ExportService atomic output tests."""

from pathlib import Path

import pytest

import export.service as service_module
from export.service import ExportService


def test_generates_all_requested_files(populated_database, tmp_path: Path) -> None:
    output = tmp_path / "output"

    result = ExportService(populated_database, output).export_all()

    assert {path.name for path in result.files} == {
        "collected_companies.csv",
        "collected_companies.xlsx",
        "all_results.csv",
        "mobile_only.csv",
        "no_phone.csv",
        "review_required.csv",
        "excluded.csv",
        "errors.csv",
    }
    assert all(path.is_file() for path in result.files)
    expected_rows = {
        "collected_companies.csv": ("株式会社1", "株式会社2"),
        "all_results.csv": ("株式会社1", "株式会社2", "株式会社3", "株式会社4", "株式会社5"),
        "mobile_only.csv": ("株式会社1",),
        "no_phone.csv": ("株式会社2",),
        "review_required.csv": ("株式会社3",),
        "excluded.csv": ("株式会社3", "株式会社4", "株式会社5"),
        "errors.csv": ("株式会社5",),
    }
    for filename, expected in expected_rows.items():
        text = (output / filename).read_text(encoding="utf-8-sig")
        assert all(value in text for value in expected)


def test_failure_preserves_existing_files_and_removes_temps(
    populated_database, tmp_path: Path
) -> None:
    output = tmp_path / "output"
    output.mkdir()
    existing = output / "collected_companies.csv"
    existing.write_text("existing", encoding="utf-8")

    class FailingExcel:
        """Exporter fake that fails during temporary generation."""

        def export(self, path: Path, snapshot: object) -> None:
            """Raise a synthetic disk error."""
            raise OSError("synthetic export failure")

    service = ExportService(populated_database, output, excel_exporter=FailingExcel())
    with pytest.raises(OSError, match="synthetic"):
        service.export_all()

    assert existing.read_text(encoding="utf-8") == "existing"
    assert not list(output.glob("*.tmp"))


def test_replace_failure_rolls_back_existing_outputs(
    populated_database, tmp_path: Path, monkeypatch
) -> None:
    """A one-time replacement error restores every previous output."""
    output = tmp_path / "output"
    output.mkdir()
    first = output / "collected_companies.csv"
    second = output / "mobile_only.csv"
    first.write_text("old-first", encoding="utf-8")
    second.write_text("old-second", encoding="utf-8")
    original_replace = service_module.os.replace
    failed = False

    def fail_once(source: Path, target: Path) -> None:
        nonlocal failed
        if not failed and Path(target) == second and str(source).endswith(".tmp"):
            failed = True
            raise OSError("synthetic replace failure")
        original_replace(source, target)

    monkeypatch.setattr(service_module.os, "replace", fail_once)

    with pytest.raises(OSError, match="replace"):
        ExportService(populated_database, output).export_all()

    assert first.read_text(encoding="utf-8") == "old-first"
    assert second.read_text(encoding="utf-8") == "old-second"
