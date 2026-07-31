"""Phase 8 Step 2 CSV exporter tests."""

from export.csv import CSVExporter
from export.models import ExportCategory
from export.repository import ExportRepository


def test_csv_has_bom_crlf_and_preserves_leading_zero(populated_database, tmp_path) -> None:
    snapshot = ExportRepository(populated_database).read_snapshot()
    path = tmp_path / "targets.csv"

    CSVExporter().export(path, snapshot.rows_for(ExportCategory.BUSINESS_TARGETS))

    content = path.read_bytes()
    assert content.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in content
    text = content.decode("utf-8-sig")
    assert "090-1234-5678" in text
    assert "001-0001" in text
    assert "090-1234-5678 | 03-1234-5678" in text
