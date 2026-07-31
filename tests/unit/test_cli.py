"""Phase 8 Step 6 minimal CLI exit-code tests."""

from pathlib import Path

from src.cli import main


def test_status_and_export_return_success(populated_database, tmp_path, capsys) -> None:
    database_path = populated_database.path

    assert main(["status"], database_path=database_path) == 0
    assert "営業対象件数" in capsys.readouterr().out
    assert main(["export"], database_path=database_path, output_dir=tmp_path) == 0
    assert (tmp_path / "collected_companies.xlsx").is_file()


def test_user_input_and_internal_errors_have_distinct_codes(tmp_path: Path) -> None:
    assert main(["unknown"], database_path=tmp_path / "none.sqlite3") == 2
    assert main(["status"], database_path=tmp_path / "none.sqlite3") == 1


def test_version_uses_distribution_version(capsys) -> None:
    """Expose the release version without loading configuration."""
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == "0.10.0"
