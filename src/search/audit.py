"""SQLite persistence for query-by-provider execution audits."""

from __future__ import annotations

from dataclasses import dataclass

from storage.sqlite import Database


@dataclass(frozen=True, slots=True)
class ProviderAuditRecord:
    """One provider execution including explicit success or failure details."""

    run_id: str
    query: str
    provider: str
    enabled: bool
    started_at: str
    finished_at: str
    http_status: int | None
    result_count: int
    accepted_count: int
    duplicate_count: int
    failure_type: str | None
    failure_message: str | None
    final_url: str | None
    elapsed_ms: int


class SearchProviderAuditRepository:
    """Store provider observations transactionally without response bodies."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def save(self, record: ProviderAuditRecord) -> None:
        """Insert one immutable provider execution record."""
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO search_provider_audit(
                       run_id, query, provider, enabled, started_at, finished_at,
                       http_status, result_count, accepted_count, duplicate_count,
                       failure_type, failure_message, final_url, elapsed_ms
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.run_id,
                    record.query,
                    record.provider,
                    int(record.enabled),
                    record.started_at,
                    record.finished_at,
                    record.http_status,
                    record.result_count,
                    record.accepted_count,
                    record.duplicate_count,
                    record.failure_type,
                    record.failure_message,
                    record.final_url,
                    record.elapsed_ms,
                ),
            )
