"""Consistent SQLite-only export snapshot reader."""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from dataclasses import replace
from urllib.parse import urlsplit

from export.models import ExportRow, ExportSnapshot
from storage.sqlite import Database


class ExportRepository:
    """Read normalized pipeline tables without invoking crawler or extractor code."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def read_snapshot(self) -> ExportSnapshot:
        """Read all export data in one consistent transaction."""
        with self.database.connect() as connection:
            connection.execute("BEGIN")
            base_rows = connection.execute(_BASE_QUERY).fetchall()
            company_ids = [int(row["company_id"]) for row in base_rows if row["company_id"]]
            phones = _read_phones(connection, company_ids)
            errors = _read_errors(connection)
            raw_rows = tuple(_to_export_row(row, phones, errors) for row in base_rows)
            orphan_errors = _read_orphan_errors(connection)
        rows, sales_rows = _deduplicate(raw_rows)
        error_rows = (*tuple(row for row in rows if row.error_message), *orphan_errors)
        return ExportSnapshot(rows, error_rows, sales_rows)


_BASE_QUERY = """
SELECT
    sr.id,
    sr.url,
    sr.provider,
    sr.rank,
    sq.query,
    sc.prefecture AS search_prefecture,
    sc.municipality AS search_municipality,
    sc.industry AS search_industry,
    p.id AS page_id,
    p.final_url,
    p.http_status,
    p.processing_status,
    p.fetch_error,
    p.fetched_at,
    p.updated_at,
    c.id AS company_id,
    c.company_name,
    c.store_name,
    c.display_name,
    c.industry AS estimated_industry,
    a.postal_code,
    a.prefecture,
    a.municipality,
    a.address,
    s.official_score,
    s.business_score,
    s.is_official,
    s.is_business_target,
    s.review_required,
    s.reasons_json,
    s.positive_signals_json,
    s.negative_signals_json
FROM search_results sr
JOIN search_queries sq ON sq.id = sr.query_id
JOIN search_conditions sc ON sc.id = sq.condition_id
LEFT JOIN pages p ON p.url = sr.url
LEFT JOIN companies c ON c.page_id = p.id
LEFT JOIN addresses a ON a.id = (
    SELECT MIN(a2.id) FROM addresses a2 WHERE a2.company_id = c.id
)
LEFT JOIN scoring_results s ON s.page_id = p.id
ORDER BY sr.id
"""


def _read_phones(
    connection: sqlite3.Connection, company_ids: list[int]
) -> dict[int, list[sqlite3.Row]]:
    grouped: dict[int, list[sqlite3.Row]] = defaultdict(list)
    if not company_ids:
        return grouped
    placeholders = ",".join("?" for _ in company_ids)
    rows = connection.execute(
        f"SELECT * FROM phones WHERE company_id IN ({placeholders}) ORDER BY id",
        company_ids,
    ).fetchall()
    for row in rows:
        grouped[int(row["company_id"])].append(row)
    return grouped


def _read_errors(connection: sqlite3.Connection) -> dict[int, str]:
    rows = connection.execute(
        """
        SELECT page_id, GROUP_CONCAT(error_type || ': ' || message, ' | ') AS message
        FROM processing_errors WHERE page_id IS NOT NULL GROUP BY page_id
        """
    ).fetchall()
    return {int(row["page_id"]): str(row["message"]) for row in rows}


def _read_orphan_errors(connection: sqlite3.Connection) -> tuple[ExportRow, ...]:
    rows = connection.execute(
        """
        SELECT e.id, e.error_type, e.message, e.created_at,
               json_extract(p.payload, '$.candidate.url') AS url,
               json_extract(p.payload, '$.candidate.query') AS query_text,
               json_extract(p.payload, '$.candidate.provider') AS provider,
               json_extract(p.payload, '$.candidate.rank') AS rank
        FROM processing_errors e
        LEFT JOIN progress p ON p.id = e.progress_id
        WHERE e.page_id IS NULL
        ORDER BY e.id
        """
    ).fetchall()
    return tuple(
        ExportRow(
            id=-int(row["id"]),
            company_name="",
            store_name="",
            display_name="",
            search_industry="",
            estimated_industry="",
            primary_phone="",
            mobile_phones="",
            fixed_phones="",
            all_phone_numbers="",
            phone_usages="",
            postal_code="",
            prefecture="",
            municipality="",
            address="",
            official_url=_str(row["url"]),
            source_url=_str(row["url"]),
            search_prefecture="",
            search_municipality="",
            search_word="",
            search_query=_str(row["query_text"]),
            search_provider=_str(row["provider"]),
            search_rank=_int(row["rank"]),
            official_score=None,
            business_score=None,
            is_official=False,
            is_business_target=False,
            review_required=False,
            exclusion_reasons=_str(row["message"]),
            positive_signals="",
            negative_signals="",
            http_status=None,
            processing_status=_str(row["error_type"]),
            fetched_at=_str(row["created_at"]),
            last_checked_at=_str(row["created_at"]),
            error_message=f"{row['error_type']}: {row['message']}",
        )
        for row in rows
    )


def _to_export_row(
    row: sqlite3.Row,
    phones: dict[int, list[sqlite3.Row]],
    errors: dict[int, str],
) -> ExportRow:
    phone_rows = phones.get(int(row["company_id"] or 0), [])
    mobile = [str(phone["number"]) for phone in phone_rows if phone["kind"] == "mobile"]
    fixed = [str(phone["number"]) for phone in phone_rows if phone["kind"] == "fixed"]
    all_phones = [str(phone["number"]) for phone in phone_rows]
    usages = [f"{phone['number']}:{phone['usage']}" for phone in phone_rows]
    reasons = _json_list(row["reasons_json"])
    negative = _json_list(row["negative_signals_json"])
    is_target = bool(row["is_business_target"])
    return ExportRow(
        id=int(row["id"]),
        company_name=_str(row["company_name"]),
        store_name=_str(row["store_name"]),
        display_name=_str(row["display_name"]),
        search_industry=_str(row["search_industry"]),
        estimated_industry=_str(row["estimated_industry"]),
        primary_phone=all_phones[0] if all_phones else "",
        mobile_phones=" | ".join(mobile),
        fixed_phones=" | ".join(fixed),
        all_phone_numbers=" | ".join(all_phones),
        phone_usages=" | ".join(usages),
        postal_code=_str(row["postal_code"]),
        prefecture=_str(row["prefecture"]),
        municipality=_str(row["municipality"]),
        address=_str(row["address"]),
        official_url=_str(row["url"]),
        source_url=_str(row["final_url"] or row["url"]),
        search_prefecture=_str(row["search_prefecture"]),
        search_municipality=_str(row["search_municipality"]),
        search_word=_str(row["search_industry"]),
        search_query=_str(row["query"]),
        search_provider=_str(row["provider"]),
        search_rank=int(row["rank"]) if row["rank"] is not None else None,
        official_score=_int(row["official_score"]),
        business_score=_int(row["business_score"]),
        is_official=bool(row["is_official"]),
        is_business_target=is_target,
        review_required=bool(row["review_required"]),
        exclusion_reasons=(
            _str(row["fetch_error"])
            or (" | ".join((*reasons, *negative)) if not is_target else "")
        ),
        positive_signals=" | ".join(_json_list(row["positive_signals_json"])),
        negative_signals=" | ".join(negative),
        http_status=_int(row["http_status"]),
        processing_status=_str(row["processing_status"]),
        fetched_at=_str(row["fetched_at"]),
        last_checked_at=_str(row["updated_at"]),
        error_message=errors.get(int(row["page_id"] or 0), ""),
    )


def _json_list(value: object) -> tuple[str, ...]:
    if not value:
        return ()
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return (str(value),)
    return tuple(str(item) for item in parsed) if isinstance(parsed, list) else (str(parsed),)


def _str(value: object) -> str:
    return "" if value is None else str(value)


def _int(value: object) -> int | None:
    return int(value) if value is not None else None


def _deduplicate(
    rows: tuple[ExportRow, ...],
) -> tuple[tuple[ExportRow, ...], tuple[ExportRow, ...]]:
    """Deduplicate exact URLs/company+address while flagging composite candidates."""
    url_groups: dict[str, list[ExportRow]] = defaultdict(list)
    for row in rows:
        url_groups[_normalized_url(row.official_url)].append(row)
    annotations: dict[int, ExportRow] = {}
    representatives: list[ExportRow] = []
    for group in url_groups.values():
        histories = " | ".join(dict.fromkeys(_history(row) for row in group))
        duplicate = len(group) > 1
        for row in group:
            annotations[row.id] = replace(
                row,
                duplicate_candidate=duplicate,
                all_search_conditions=histories,
            )
        representatives.append(annotations[group[0].id])

    composite_groups: dict[tuple[str, str], list[ExportRow]] = defaultdict(list)
    for row in representatives:
        key = (_normalized_text(row.company_name), _normalized_text(row.address))
        if all(key):
            composite_groups[key].append(row)
    removed_ids: set[int] = set()
    for group in composite_groups.values():
        if len(group) < 2:
            continue
        combined_history = " | ".join(
            dict.fromkeys(row.all_search_conditions for row in group)
        )
        first = group[0]
        annotations[first.id] = replace(
            annotations[first.id],
            duplicate_candidate=True,
            all_search_conditions=combined_history,
        )
        removed_ids.update(row.id for row in group[1:])
        for row in group[1:]:
            annotations[row.id] = replace(annotations[row.id], duplicate_candidate=True)

    # Name+phone is only a review flag; it never forces an entity merge.
    candidate_groups: dict[tuple[str, str], list[ExportRow]] = defaultdict(list)
    for row in representatives:
        key = (_normalized_text(row.company_name), row.primary_phone)
        if all(key):
            candidate_groups[key].append(row)
    for group in candidate_groups.values():
        if len(group) > 1:
            for row in group:
                annotations[row.id] = replace(annotations[row.id], duplicate_candidate=True)

    annotated = tuple(annotations[row.id] for row in rows)
    sales = tuple(
        annotations[row.id] for row in representatives if row.id not in removed_ids
    )
    return annotated, sales


def _normalized_url(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    path = parts.path.rstrip("/") or "/"
    return f"{host}{path}"


def _normalized_text(value: str) -> str:
    return "".join(value.split()).lower()


def _history(row: ExportRow) -> str:
    return (
        f"{row.search_prefecture}/{row.search_municipality}/"
        f"{row.search_word} [{row.search_query}]"
    )
