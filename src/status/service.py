"""SQLite-only status aggregation without presentation side effects."""

from __future__ import annotations

import sqlite3

from status.models import StatusSnapshot
from storage.sqlite import Database


class StatusService:
    """Aggregate pipeline and export-relevant counts from SQLite."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def get_status(self) -> StatusSnapshot:
        """Return one consistent display model without printing."""
        with self.database.connect() as connection:
            connection.execute("BEGIN")
            condition_counts = {
                str(row["status"]): int(row["count"])
                for row in connection.execute(
                    "SELECT status, COUNT(*) AS count FROM search_conditions GROUP BY status"
                )
            }
            business = _count(
                connection,
                "SELECT COUNT(*) FROM scoring_results WHERE is_business_target = 1",
            )
            official = _count(
                connection,
                "SELECT COUNT(*) FROM scoring_results WHERE is_official = 1",
            )
            mobile = _count(connection, "SELECT COUNT(*) FROM phones WHERE kind = 'mobile'")
            no_phone = _count(
                connection,
                """
                SELECT COUNT(*) FROM companies c
                WHERE NOT EXISTS (SELECT 1 FROM phones p WHERE p.company_id = c.id)
                """,
            )
            review = _count(
                connection,
                "SELECT COUNT(*) FROM scoring_results WHERE review_required = 1",
            )
            excluded = _count(
                connection,
                "SELECT COUNT(*) FROM scoring_results WHERE is_business_target = 0",
            )
            retry = _count(
                connection,
                """
                SELECT COUNT(*) FROM progress
                WHERE status = 'pending' AND available_at IS NOT NULL
                """,
            )
            errors = _count(connection, "SELECT COUNT(*) FROM processing_errors")
            today = _count(
                connection,
                "SELECT COUNT(*) FROM pages WHERE DATE(fetched_at) = DATE('now')",
            )
            total = _count(connection, "SELECT COUNT(*) FROM pages")
            urls = tuple(
                str(row["url"])
                for row in connection.execute(
                    """
                    SELECT json_extract(payload, '$.candidate.url') AS url
                    FROM progress WHERE status = 'running'
                    """
                )
                if row["url"]
            )
            retry_row = connection.execute(
                """
                SELECT MIN(available_at) AS next_retry_at FROM progress
                WHERE status = 'pending' AND available_at IS NOT NULL
                """
            ).fetchone()
        return StatusSnapshot(
            sum(condition_counts.values()),
            condition_counts.get("completed", 0),
            condition_counts.get("pending", 0),
            condition_counts.get("processing", 0),
            business,
            official,
            mobile,
            no_phone,
            review,
            excluded,
            retry,
            errors,
            today,
            total,
            urls,
            str(retry_row["next_retry_at"]) if retry_row["next_retry_at"] else None,
        )


def _count(connection: sqlite3.Connection, query: str) -> int:
    row = connection.execute(query).fetchone()
    return int(row[0])
