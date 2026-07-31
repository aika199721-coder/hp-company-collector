"""Review-oriented live validation workbook and CSV generation."""

from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from export.models import ExportRow
from export.repository import ExportRepository
from live.review import REVIEW_HEADERS, ManualReviewService
from storage.sqlite import Database

LIVE_SHEETS = ("採用候補", "要確認", "除外", "HTTP監査", "検索結果", "エラー", "検証概要")
_CANDIDATE_HEADERS = (
    "法人名",
    "店舗名",
    "電話番号",
    "住所",
    "推定業種",
    "公式スコア",
    "営業対象スコア",
    "抽出元",
    "判定理由",
    "元ページURL",
    "検索順位",
    "手動確認欄",
    "誤抽出メモ欄",
)


class LiveReportService:
    """Generate live review artifacts exclusively from SQLite metadata/results."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def export(self, workbook_path: Path, review_csv_path: Path, run_id: str = "") -> None:
        """Write all required sheets and a non-destructive review template."""
        snapshot = ExportRepository(self._database).read_snapshot()
        workbook = Workbook()
        workbook.remove(workbook.active)
        partitions = {
            "採用候補": tuple(row for row in snapshot.sales_rows if row.is_business_target),
            "要確認": tuple(row for row in snapshot.rows if row.review_required),
            "除外": tuple(row for row in snapshot.rows if not row.is_business_target),
            "エラー": snapshot.errors,
        }
        for name in LIVE_SHEETS:
            sheet = workbook.create_sheet(name)
            if name in partitions:
                _candidate_sheet(sheet, partitions[name])
            elif name == "HTTP監査":
                _database_sheet(self._database, sheet, "http_audit_logs", run_id)
            elif name == "検索結果":
                _search_sheet(self._database, sheet)
            else:
                _summary_sheet(self._database, sheet, snapshot.rows, run_id)
        workbook_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = workbook_path.with_suffix(".xlsx.tmp")
        workbook.save(temporary)
        temporary.replace(workbook_path)
        if not review_csv_path.exists():
            _review_csv(review_csv_path, snapshot.rows)


def _candidate_sheet(sheet: object, rows: tuple[ExportRow, ...]) -> None:
    sheet.append(list(_CANDIDATE_HEADERS))
    for row in rows:
        sheet.append(
            [
                row.company_name,
                row.store_name,
                row.all_phone_numbers,
                row.address,
                row.estimated_industry,
                row.official_score,
                row.business_score,
                row.source_url,
                "; ".join(filter(None, (row.positive_signals, row.negative_signals))),
                row.source_url,
                row.search_rank,
                "未確認",
                "",
            ]
        )
    _style(sheet)


def _database_sheet(database: Database, sheet: object, table: str, run_id: str) -> None:
    with database.connect() as connection:
        condition = " WHERE run_id = ?" if run_id else ""
        params = (run_id,) if run_id else ()
        rows = connection.execute(
            f"SELECT * FROM {table}{condition} ORDER BY id", params
        ).fetchall()
    headers = list(rows[0].keys()) if rows else ["id", "run_id", "result_category", "error_type"]
    sheet.append(headers)
    for row in rows:
        sheet.append([row[key] for key in headers])
    _style(sheet)


def _search_sheet(database: Database, sheet: object) -> None:
    headers = ["URL", "検索クエリ", "Provider", "順位", "タイトル"]
    sheet.append(headers)
    with database.connect() as connection:
        rows = connection.execute(
            """SELECT sr.url, sq.query, sr.provider, sr.rank, sr.title
               FROM search_results sr
               JOIN search_queries sq ON sq.id = sr.query_id
               ORDER BY sr.id"""
        ).fetchall()
    for row in rows:
        sheet.append(list(row))
    _style(sheet)


def _summary_sheet(
    database: Database, sheet: object, rows: tuple[ExportRow, ...], run_id: str
) -> None:
    with database.connect() as connection:
        audits = connection.execute(
            "SELECT COUNT(*) FROM http_audit_logs WHERE run_id = ? OR ? = ''", (run_id, run_id)
        ).fetchone()[0]
        condition = connection.execute(
            """SELECT prefecture, municipality, industry FROM search_conditions
               ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        query = connection.execute(
            "SELECT query FROM search_queries ORDER BY id DESC LIMIT 1"
        ).fetchone()
        run = connection.execute(
            """SELECT started_at, finished_at FROM runs
               WHERE command = 'live-check' ORDER BY started_at DESC LIMIT 1"""
        ).fetchone()
    values = {
        "検索条件": " ".join(str(value) for value in condition) if condition else "",
        "検索クエリ": str(query[0]) if query else "",
        "発見URL数": len(rows),
        "HTTP取得数": audits,
        "robots拒否数": sum(row.processing_status == "robots_denied" for row in rows),
        "公式候補数": sum(row.is_official for row in rows),
        "営業対象数": sum(row.is_business_target for row in rows),
        "携帯番号取得数": sum(bool(row.mobile_phones) for row in rows),
        "固定電話取得数": sum(bool(row.fixed_phones) for row in rows),
        "電話番号なし数": sum(not row.all_phone_numbers for row in rows),
        "要確認数": sum(row.review_required for row in rows),
        "除外数": sum(not row.is_business_target for row in rows),
        "エラー数": sum(bool(row.error_message) for row in rows),
        "開始時刻": str(run[0]) if run else "",
        "終了時刻": str(run[1]) if run else "",
        "総実行時間": _duration(run),
        "生成時刻": datetime.now(UTC).isoformat(),
    }
    accuracy = ManualReviewService(database).accuracy()
    values.update(
        {
            "レビュー件数": accuracy.review_count,
            "電話番号正解率": accuracy.phone_accuracy,
            "公式サイトprecision": accuracy.official_precision,
            "営業対象precision": accuracy.business_precision,
            "false positive件数": accuracy.false_positive_count,
            "false negative件数": accuracy.false_negative_count,
            "統計的に十分": accuracy.statistically_sufficient,
        }
    )
    sheet.append(["項目", "値"])
    for key, value in values.items():
        sheet.append([key, value])
    _style(sheet)


def _review_csv(path: Path, rows: tuple[ExportRow, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\r\n")
        writer.writerow(REVIEW_HEADERS)
        for row in rows:
            writer.writerow([row.source_url, *("未確認" for _ in range(8)), ""])


def _style(sheet: object) -> None:
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def _duration(run: object) -> str:
    if not run or not run[0] or not run[1]:
        return ""
    try:
        elapsed = datetime.fromisoformat(run[1]) - datetime.fromisoformat(run[0])
    except ValueError:
        return ""
    return str(elapsed)
