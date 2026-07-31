"""Transactional SQLite persistence for pipeline discoveries and outcomes."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from crawler.result import FetchResult
from extractor.facade import ExtractionResult
from scoring.models import ScoringResult
from storage.sqlite import Database

if TYPE_CHECKING:
    from pipeline.models import CandidateUrl, ProcessingStatus, SearchCondition


class PipelineRepository:
    """Persist search history, raw pages, extraction, scoring, and errors."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def create_condition(self, condition: SearchCondition) -> int:
        """Insert one run condition and return its ID."""
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO search_conditions(
                    prefecture, municipality, industry, max_results, enabled
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    condition.prefecture,
                    condition.municipality,
                    condition.industry,
                    condition.max_results,
                    int(condition.enabled),
                ),
            )
        return int(cursor.lastrowid)

    def record_candidate(self, condition_id: int, candidate: CandidateUrl) -> int:
        """Store query and URL discovery history for a condition."""
        with self.database.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO search_queries(condition_id, query) VALUES (?, ?)",
                (condition_id, candidate.query),
            )
            query = connection.execute(
                "SELECT id FROM search_queries WHERE condition_id = ? AND query = ?",
                (condition_id, candidate.query),
            ).fetchone()
            assert query is not None
            connection.execute(
                """
                INSERT OR IGNORE INTO search_results(
                    query_id, url, provider, rank, title, snippet
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    query["id"],
                    candidate.url,
                    candidate.provider,
                    candidate.rank,
                    candidate.title,
                    candidate.snippet,
                ),
            )
            row = connection.execute(
                "SELECT id FROM search_results WHERE query_id = ? AND url = ?",
                (query["id"], candidate.url),
            ).fetchone()
        assert row is not None
        return int(row["id"])

    def set_condition_status(self, condition_id: int, status: str) -> None:
        """Persist pending, processing, or completed condition state."""
        if status not in {"pending", "processing", "completed"}:
            raise ValueError(f"invalid condition status: {status}")
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE search_conditions
                SET status = ?,
                    completed_at = CASE
                        WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL
                    END
                WHERE id = ?
                """,
                (status, status, condition_id),
            )

    def terminal_status(self, url: str) -> str | None:
        """Return a terminal page status when a URL must not be fetched again."""
        retryable = {
            "http_429",
            "http_503",
            "timeout",
            "transport_error",
        }
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT processing_status FROM pages WHERE url = ?", (url,)
            ).fetchone()
        if row is None or row["processing_status"] in retryable:
            return None
        return str(row["processing_status"])

    def save_prefetch_exclusion(self, url: str, reason: str) -> int:
        """Persist a rejected search result without fetching its URL."""
        with self.database.connect() as connection:
            connection.execute(
                """INSERT INTO pages(url, processing_status, fetch_error)
                   VALUES (?, 'excluded', ?)
                   ON CONFLICT(url) DO UPDATE SET
                       processing_status = 'excluded', fetch_error = excluded.fetch_error,
                       updated_at = CURRENT_TIMESTAMP""",
                (url, reason),
            )
            row = connection.execute("SELECT id FROM pages WHERE url = ?", (url,)).fetchone()
            assert row is not None
            connection.execute(
                """INSERT INTO processing_errors(page_id, error_type, message)
                   VALUES (?, 'prefetch_excluded', ?)""",
                (row["id"], reason),
            )
        return int(row["id"])

    def save_page(self, url: str, fetch: FetchResult | None, status: ProcessingStatus) -> int:
        """Upsert raw transport data and processing status separately from company data."""
        values = (
            url,
            fetch.final_url if fetch else None,
            fetch.status_code if fetch else None,
            json.dumps(dict(fetch.headers), ensure_ascii=False) if fetch else "{}",
            fetch.content if fetch else None,
            fetch.encoding if fetch else None,
            fetch.error if fetch else None,
            status.value,
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO pages(
                    url, final_url, http_status, headers_json, content,
                    encoding, fetch_error, processing_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    final_url = excluded.final_url,
                    http_status = excluded.http_status,
                    headers_json = excluded.headers_json,
                    content = excluded.content,
                    encoding = excluded.encoding,
                    fetch_error = excluded.fetch_error,
                    processing_status = excluded.processing_status,
                    updated_at = CURRENT_TIMESTAMP
                """,
                values,
            )
            row = connection.execute("SELECT id FROM pages WHERE url = ?", (url,)).fetchone()
        assert row is not None
        return int(row["id"])

    def save_extraction(self, page_id: int, extraction: ExtractionResult) -> int:
        """Upsert company and replace its normalized phone/address children."""
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO companies(
                    page_id, company_name, store_name, display_name, industry
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(page_id) DO UPDATE SET
                    company_name = excluded.company_name,
                    store_name = excluded.store_name,
                    display_name = excluded.display_name,
                    industry = excluded.industry
                """,
                (
                    page_id,
                    _value(extraction.company_name),
                    _value(extraction.store_name),
                    _value(extraction.display_name),
                    _value(extraction.industry),
                ),
            )
            company = connection.execute(
                "SELECT id FROM companies WHERE page_id = ?", (page_id,)
            ).fetchone()
            assert company is not None
            company_id = int(company["id"])
            connection.execute("DELETE FROM phones WHERE company_id = ?", (company_id,))
            connection.execute("DELETE FROM addresses WHERE company_id = ?", (company_id,))
            connection.executemany(
                """
                INSERT INTO phones(company_id, number, kind, usage, source)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (company_id, phone.number, phone.kind, phone.usage, phone.source)
                    for phone in extraction.phones
                ],
            )
            if extraction.address:
                address = extraction.address
                connection.execute(
                    """
                    INSERT INTO addresses(
                        company_id, address, postal_code, prefecture, municipality, source
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company_id,
                        address.address,
                        address.postal_code,
                        address.prefecture,
                        address.municipality,
                        address.source,
                    ),
                )
        return company_id

    def save_scoring(self, page_id: int, scoring: ScoringResult) -> None:
        """Persist scores and complete reason/signal JSON arrays."""
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO scoring_results(
                    page_id, official_score, business_score, is_official,
                    is_business_target, review_required, reasons_json,
                    positive_signals_json, negative_signals_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(page_id) DO UPDATE SET
                    official_score = excluded.official_score,
                    business_score = excluded.business_score,
                    is_official = excluded.is_official,
                    is_business_target = excluded.is_business_target,
                    review_required = excluded.review_required,
                    reasons_json = excluded.reasons_json,
                    positive_signals_json = excluded.positive_signals_json,
                    negative_signals_json = excluded.negative_signals_json
                """,
                (
                    page_id,
                    scoring.official_score,
                    scoring.business_score,
                    int(scoring.is_official),
                    int(scoring.is_business_target),
                    int(scoring.review_required),
                    json.dumps(scoring.reasons, ensure_ascii=False),
                    json.dumps(scoring.positive_signals, ensure_ascii=False),
                    json.dumps(scoring.negative_signals, ensure_ascii=False),
                ),
            )

    def save_error(
        self, page_id: int | None, progress_id: int, error_type: str, message: str
    ) -> None:
        """Persist a bounded per-candidate error without stopping the worker."""
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO processing_errors(page_id, progress_id, error_type, message)
                VALUES (?, ?, ?, ?)
                """,
                (page_id, progress_id, error_type, message[:2000]),
            )

    def pause_domain(self, url: str, until: datetime, reason: str) -> None:
        """Persist an origin-wide retry pause."""
        origin = _origin(url)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO domain_pauses(origin, paused_until, reason)
                VALUES (?, ?, ?)
                ON CONFLICT(origin) DO UPDATE SET
                    paused_until = excluded.paused_until,
                    reason = excluded.reason,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (origin, _timestamp(until), reason),
            )

    def domain_pause_until(self, url: str) -> str | None:
        """Return the persisted origin pause timestamp."""
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT paused_until FROM domain_pauses WHERE origin = ?", (_origin(url),)
            ).fetchone()
        return str(row["paused_until"]) if row else None


def _value(item: object) -> str | None:
    value = getattr(item, "value", None)
    return str(value) if value is not None else None


def _origin(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("url must be absolute HTTP(S)")
    return f"{parts.scheme.lower()}://{parts.hostname.lower()}"


def _timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%Y-%m-%d %H:%M:%S")
