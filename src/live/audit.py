"""Metadata-only HTTP audit persistence for live validation."""

from __future__ import annotations

from dataclasses import dataclass

from storage.sqlite import Database


@dataclass(frozen=True, slots=True)
class HttpAuditEntry:
    """One HTTP attempt without body, cookie, or authentication data."""

    run_id: str
    requested_url: str
    final_url: str
    domain: str
    requested_at: str
    finished_at: str
    elapsed_ms: int
    http_status: int | None
    content_type: str
    content_length: int
    encoding: str
    redirect_count: int
    robots_allowed: bool
    rate_limit_delay: float
    playwright_used: bool
    result_category: str
    error_type: str | None


class HttpAuditRepository:
    """Append and read metadata-only audit rows transactionally."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def save(self, entry: HttpAuditEntry) -> None:
        """Insert one parameterized audit record."""
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO http_audit_logs (
                       run_id, requested_url, final_url, domain, requested_at, finished_at,
                       elapsed_ms, http_status, content_type, content_length, encoding,
                       redirect_count, robots_allowed, rate_limit_delay, playwright_used,
                       result_category, error_type
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.run_id,
                    entry.requested_url,
                    entry.final_url,
                    entry.domain,
                    entry.requested_at,
                    entry.finished_at,
                    entry.elapsed_ms,
                    entry.http_status,
                    entry.content_type,
                    entry.content_length,
                    entry.encoding,
                    entry.redirect_count,
                    int(entry.robots_allowed),
                    entry.rate_limit_delay,
                    int(entry.playwright_used),
                    entry.result_category,
                    entry.error_type,
                ),
            )

    def list_for_run(self, run_id: str) -> tuple[HttpAuditEntry, ...]:
        """Return audits in request order."""
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM http_audit_logs WHERE run_id = ? ORDER BY id", (run_id,)
            ).fetchall()
        return tuple(
            HttpAuditEntry(*(row[key] for key in HttpAuditEntry.__dataclass_fields__))
            for row in rows
        )
