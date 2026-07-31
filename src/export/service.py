"""Atomic multi-format export orchestration from one SQLite snapshot."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from export.csv import CSVExporter
from export.excel import ExcelExporter
from export.models import ExportCategory, ExportSnapshot
from export.repository import ExportRepository
from storage.sqlite import Database


class ExcelWriter(Protocol):
    """Injectable workbook writer used for failure tests."""

    def export(self, path: Path, snapshot: ExportSnapshot) -> None:
        """Write a workbook to a temporary path."""


@dataclass(frozen=True, slots=True)
class ExportServiceResult:
    """Paths replaced after a successful export generation."""

    files: tuple[Path, ...]


class ExportService:
    """Generate all files from one snapshot and atomically replace destinations."""

    def __init__(
        self,
        database: Database,
        output_dir: Path,
        *,
        csv_exporter: CSVExporter | None = None,
        excel_exporter: ExcelWriter | None = None,
    ) -> None:
        self._repository = ExportRepository(database)
        self._output = Path(output_dir)
        self._csv = csv_exporter or CSVExporter()
        self._excel = excel_exporter or ExcelExporter()

    def export_all(self) -> ExportServiceResult:
        """Generate temporary files first and replace normal files only on success."""
        self._output.mkdir(parents=True, exist_ok=True)
        snapshot = self._repository.read_snapshot()
        specifications = (
            ("collected_companies.csv", ExportCategory.BUSINESS_TARGETS),
            ("all_results.csv", ExportCategory.ALL_RESULTS),
            ("mobile_only.csv", ExportCategory.MOBILE_ONLY),
            ("no_phone.csv", ExportCategory.NO_PHONE),
            ("review_required.csv", ExportCategory.REVIEW_REQUIRED),
            ("excluded.csv", ExportCategory.EXCLUDED),
            ("errors.csv", ExportCategory.ERRORS),
        )
        temporary: list[tuple[Path, Path]] = []
        backups: list[tuple[Path, Path]] = []
        installed: list[Path] = []
        try:
            for filename, category in specifications:
                target = self._output / filename
                temp = _temporary_path(target)
                self._csv.export(temp, snapshot.rows_for(category))
                temporary.append((temp, target))
            excel_target = self._output / "collected_companies.xlsx"
            excel_temp = _temporary_path(excel_target)
            self._excel.export(excel_temp, snapshot)
            temporary.append((excel_temp, excel_target))
            for _, target in temporary:
                if target.exists():
                    backup = target.with_name(f".{target.name}.{uuid.uuid4().hex}.bak")
                    os.replace(target, backup)
                    backups.append((backup, target))
            for temp, target in temporary:
                os.replace(temp, target)
                installed.append(target)
            for backup, _ in backups:
                backup.unlink(missing_ok=True)
        except Exception:
            for temp, _ in temporary:
                temp.unlink(missing_ok=True)
            for target in installed:
                target.unlink(missing_ok=True)
            for backup, target in backups:
                if backup.exists():
                    os.replace(backup, target)
            for path in self._output.glob(".*.tmp"):
                path.unlink(missing_ok=True)
            raise
        return ExportServiceResult(tuple(target for _, target in temporary))


def _temporary_path(target: Path) -> Path:
    return target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
