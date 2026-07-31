"""Safe openpyxl workbook exporter with fixed Japanese sheets."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from export.models import HEADERS, ExportCategory, ExportRow, ExportSnapshot

SHEET_CATEGORIES = {
    "営業対象": ExportCategory.BUSINESS_TARGETS,
    "携帯あり": ExportCategory.MOBILE_ONLY,
    "要確認": ExportCategory.REVIEW_REQUIRED,
    "電話なし": ExportCategory.NO_PHONE,
    "除外": ExportCategory.EXCLUDED,
    "エラー": ExportCategory.ERRORS,
    "全件": None,
    "検索履歴": ExportCategory.ALL_RESULTS,
}
SHEET_NAMES = tuple(SHEET_CATEGORIES)
_TEXT_FIELDS = {
    "primary_phone",
    "mobile_phones",
    "fixed_phones",
    "all_phone_numbers",
    "postal_code",
}
_URL_FIELDS = {"official_url", "source_url"}


class ExcelExporter:
    """Write one workbook directly from an immutable SQLite snapshot."""

    def export(self, path: Path, snapshot: ExportSnapshot) -> None:
        """Create all sheets, including headers for empty partitions."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        workbook.remove(workbook.active)
        for sheet_name, category in SHEET_CATEGORIES.items():
            sheet = workbook.create_sheet(sheet_name)
            rows = snapshot.sales_rows if category is None else snapshot.rows_for(category)
            _write_sheet(sheet, rows)
        try:
            workbook.save(path)
        except OSError:
            path.unlink(missing_ok=True)
            raise


def _write_sheet(sheet: Worksheet, rows: tuple[ExportRow, ...]) -> None:
    sheet.append([header for _, header in HEADERS])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append([_safe_excel_value(getattr(row, field)) for field, _ in HEADERS])
        row_index = sheet.max_row
        for column, (field, _) in enumerate(HEADERS, 1):
            cell = sheet.cell(row_index, column)
            if field in _TEXT_FIELDS:
                cell.number_format = "@"
            if field in _URL_FIELDS and cell.value:
                cell.hyperlink = str(cell.value)
                cell.style = "Hyperlink"
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column, (_, header) in enumerate(HEADERS, 1):
        values = [header, *(sheet.cell(row, column).value for row in range(2, sheet.max_row + 1))]
        width = min(50, max(10, max(len(str(value or "")) for value in values) + 2))
        sheet.column_dimensions[get_column_letter(column)].width = width


def _safe_excel_value(value: object) -> str | int:
    if isinstance(value, bool):
        return "はい" if value else "いいえ"
    if value is None:
        return ""
    if isinstance(value, int):
        return value
    text = str(value)
    if text.startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text[:32767]
