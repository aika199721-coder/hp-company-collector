"""Offline live report, review history, and accuracy integration tests."""

import csv
from pathlib import Path

import pytest
from openpyxl import load_workbook

from live.report import LIVE_SHEETS, LiveReportService
from live.review import REVIEW_HEADERS, ManualReviewService


def _review(path: Path, url: str, judgment: str = "OK") -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(REVIEW_HEADERS)
        writer.writerow([url, *(judgment for _ in range(8)), "確認メモ"])


def test_live_report_has_all_sheets_and_generates_review_csv(
    populated_database, tmp_path: Path
) -> None:
    workbook = tmp_path / "live_validation_report.xlsx"
    review = tmp_path / "live_review.csv"

    LiveReportService(populated_database).export(workbook, review)

    assert load_workbook(workbook).sheetnames == list(LIVE_SHEETS)
    assert review.read_bytes().startswith(b"\xef\xbb\xbf")
    assert "未確認" in review.read_text(encoding="utf-8-sig")


def test_live_report_contains_provider_audit(populated_database, tmp_path: Path) -> None:
    with populated_database.connect() as connection:
        connection.execute(
            """INSERT INTO search_provider_audit(
                   run_id, query, provider, enabled, started_at, finished_at,
                   result_count, accepted_count, duplicate_count, elapsed_ms
               ) VALUES ('run-p', '那覇市 美容室', 'duckduckgo_html', 1,
                         '2026-01-01', '2026-01-01', 5, 4, 1, 10)"""
        )
        condition_id = connection.execute("SELECT MIN(id) FROM search_conditions").fetchone()[0]
        connection.execute(
            "INSERT INTO search_queries(condition_id, query) VALUES (?, '那覇 美容院')",
            (condition_id,),
        )
        query_id = connection.execute("SELECT MAX(id) FROM search_queries").fetchone()[0]
        connection.execute(
            """INSERT INTO search_results(
                   query_id, url, provider, rank, title, snippet, relevance_score
                   , normalized_url
               ) VALUES (?, 'https://mobile.example/', 'duckduckgo_html', 2,
                         '美容室', '那覇市', 1.0, 'https://mobile.example')""",
            (query_id,),
        )
    workbook = tmp_path / "report.xlsx"

    LiveReportService(populated_database).export(
        workbook, tmp_path / "review.csv", provider_run_id="run-p"
    )

    loaded = load_workbook(workbook)
    audit = loaded["Provider監査"]
    assert audit.max_row == 2
    assert audit.cell(2, 4).value == "duckduckgo_html"
    summary = {row[0]: row[1] for row in loaded["検証概要"].iter_rows(values_only=True)}
    assert summary["Provider横断重複数"] >= 1
    assert summary["Provider duckduckgo_html 実行回数"] == 1


def test_review_import_preserves_history_and_automatic_scoring(
    populated_database, tmp_path: Path
) -> None:
    path = tmp_path / "review.csv"
    _review(path, "https://official.example/")
    service = ManualReviewService(populated_database)
    with populated_database.connect() as connection:
        before = connection.execute("SELECT is_business_target FROM scoring_results").fetchone()[0]

    assert service.import_csv(path, "reviewer-a") == 1
    assert service.import_csv(path, "reviewer-b") == 1
    report = service.accuracy()

    with populated_database.connect() as connection:
        review_count = connection.execute("SELECT COUNT(*) FROM manual_reviews").fetchone()[0]
        after = connection.execute("SELECT is_business_target FROM scoring_results").fetchone()[0]
    assert review_count == 2
    assert before == after
    assert report.company_name_accuracy == 1.0
    assert report.statistically_sufficient is False


def test_unknown_review_value_has_row_number(populated_database, tmp_path: Path) -> None:
    path = tmp_path / "review.csv"
    _review(path, "https://official.example/", "不明")

    with pytest.raises(ValueError, match="row 2"):
        ManualReviewService(populated_database).import_csv(path)
