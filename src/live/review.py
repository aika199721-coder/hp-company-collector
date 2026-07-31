"""Manual review CSV validation, history, and accuracy aggregation."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from storage.sqlite import Database

JUDGMENTS = frozenset({"OK", "NG", "要確認", "未確認"})
REVIEW_HEADERS = (
    "URL",
    "法人名判定",
    "店舗名判定",
    "電話番号判定",
    "住所判定",
    "業種判定",
    "公式サイト判定",
    "営業対象判定",
    "総合判定",
    "メモ",
)
_JUDGMENT_FIELDS = REVIEW_HEADERS[1:9]


@dataclass(frozen=True, slots=True)
class AccuracyReport:
    """Review-derived rates; None means no eligible reviewed sample."""

    review_count: int
    company_name_accuracy: float | None
    store_name_accuracy: float | None
    phone_accuracy: float | None
    address_accuracy: float | None
    industry_accuracy: float | None
    official_precision: float | None
    business_precision: float | None
    false_positive_count: int
    false_negative_count: int
    review_required_rate: float | None
    statistically_sufficient: bool


class ManualReviewService:
    """Append validated reviews without changing automatic scoring rows."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def import_csv(self, path: Path, reviewer: str | None = None) -> int:
        """Validate every row, then append all reviews in one transaction."""
        with Path(path).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = [
                header for header in REVIEW_HEADERS if header not in (reader.fieldnames or ())
            ]
            if missing:
                raise ValueError(f"Missing review columns: {', '.join(missing)}")
            rows = [self._validate(row, number) for number, row in enumerate(reader, 2)]
        with self._database.connect() as connection:
            connection.executemany(
                """INSERT INTO manual_reviews (
                       url, company_name_judgment, store_name_judgment, phone_judgment,
                       address_judgment, industry_judgment, official_site_judgment,
                       business_target_judgment, overall_judgment, note, reviewer
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [(*row, reviewer) for row in rows],
            )
        return len(rows)

    def accuracy(self) -> AccuracyReport:
        """Calculate accuracy and precision from the latest review per URL."""
        with self._database.connect() as connection:
            rows = connection.execute(
                """SELECT mr.*, s.is_official, s.is_business_target, s.review_required
                   FROM manual_reviews mr
                   JOIN (SELECT url, MAX(id) AS id FROM manual_reviews GROUP BY url) latest
                     ON latest.id = mr.id
                   LEFT JOIN pages p ON p.url = mr.url OR p.final_url = mr.url
                   LEFT JOIN scoring_results s ON s.page_id = p.id"""
            ).fetchall()
        extraction_rates = [
            _rate(rows, field)
            for field in (
                "company_name_judgment",
                "store_name_judgment",
                "phone_judgment",
                "address_judgment",
                "industry_judgment",
            )
        ]
        rates = [
            *extraction_rates,
            _precision(rows, "is_official", "official_site_judgment"),
            _precision(rows, "is_business_target", "business_target_judgment"),
        ]
        false_positive = sum(
            bool(row["is_business_target"]) and row["business_target_judgment"] == "NG"
            for row in rows
        )
        false_negative = sum(
            row["is_business_target"] == 0 and row["business_target_judgment"] == "OK"
            for row in rows
        )
        review_rate = (
            sum(bool(row["review_required"]) for row in rows) / len(rows) if rows else None
        )
        return AccuracyReport(
            len(rows), *rates, false_positive, false_negative, review_rate, len(rows) >= 30
        )

    @staticmethod
    def _validate(row: dict[str, str], number: int) -> tuple[str, ...]:
        url = row["URL"].strip()
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError(f"row {number}: invalid URL")
        values = tuple(row[field].strip() for field in _JUDGMENT_FIELDS)
        unknown = [value for value in values if value not in JUDGMENTS]
        if unknown:
            raise ValueError(f"row {number}: unknown judgment: {unknown[0]}")
        return (url, *values, row["メモ"].strip())


def _rate(rows: list[object], field: str) -> float | None:
    eligible = [row[field] for row in rows if row[field] in {"OK", "NG"}]
    return eligible.count("OK") / len(eligible) if eligible else None


def _precision(rows: list[object], automatic: str, judgment: str) -> float | None:
    eligible = [row[judgment] for row in rows if row[automatic] and row[judgment] in {"OK", "NG"}]
    return eligible.count("OK") / len(eligible) if eligible else None
