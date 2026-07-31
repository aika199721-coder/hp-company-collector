"""UTF-8 BOM and CRLF CSV exporter for Windows sales workflows."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from export.models import HEADERS, ExportRow


class CSVExporter:
    """Write flattened export rows without reading any other data source."""

    def export(self, path: Path, rows: Iterable[ExportRow]) -> None:
        """Write a complete CSV with BOM, CRLF, and textual phone/postal values."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle, lineterminator="\r\n")
                writer.writerow(header for _, header in HEADERS)
                for row in rows:
                    writer.writerow(_csv_value(getattr(row, field)) for field, _ in HEADERS)
        except OSError:
            if path.exists():
                path.unlink(missing_ok=True)
            raise


def _csv_value(value: object) -> str | int:
    if isinstance(value, bool):
        return "はい" if value else "いいえ"
    if value is None:
        return ""
    if isinstance(value, int):
        return value
    text = str(value)
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text
