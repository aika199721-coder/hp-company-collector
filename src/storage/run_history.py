"""Transactional persistence for application runs and shutdown events."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from __version__ import __version__
from storage.sqlite import Database


class RunHistoryRepository:
    """Store auditable run-level and condition-level application history."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def start(self, command: str, input_file: str, config_file: str, total: int) -> str:
        """Create a running record and return its generated identifier."""
        run_id = uuid4().hex
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO runs (
                       run_id, command, started_at, status, input_file, config_file,
                       database_file, conditions_total, application_version
                   ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    command,
                    datetime.now(UTC).isoformat(),
                    input_file,
                    config_file,
                    str(self._database.path),
                    total,
                    __version__,
                ),
            )
        return run_id

    def start_condition(self, run_id: str, index: int) -> None:
        """Mark one condition as running."""
        with self._database.connect() as connection:
            connection.execute(
                "INSERT INTO run_conditions (run_id, condition_index, status) VALUES (?, ?, ?)",
                (run_id, index, "running"),
            )

    def finish_condition(
        self, run_id: str, index: int, status: str, summary: dict[str, Any], error: str | None
    ) -> None:
        """Persist a condition outcome."""
        with self._database.connect() as connection:
            connection.execute(
                """UPDATE run_conditions SET status = ?, summary_json = ?, error_message = ?,
                       finished_at = ? WHERE run_id = ? AND condition_index = ?""",
                (status, json.dumps(summary), error, datetime.now(UTC).isoformat(), run_id, index),
            )

    def finish(
        self,
        run_id: str,
        status: str,
        completed: int,
        targets: int,
        processed: int,
        errors: int,
        reason: str | None = None,
    ) -> None:
        """Finalize aggregate counters for a run."""
        with self._database.connect() as connection:
            connection.execute(
                """UPDATE runs SET finished_at = ?, status = ?, conditions_completed = ?,
                       business_targets = ?, processed_candidates = ?, error_count = ?,
                       shutdown_reason = ? WHERE run_id = ?""",
                (
                    datetime.now(UTC).isoformat(), status, completed, targets,
                    processed, errors, reason, run_id,
                ),
            )

    def shutdown(self, run_id: str, reason: str, signal_name: str | None) -> None:
        """Append a shutdown audit event."""
        with self._database.connect() as connection:
            connection.execute(
                "INSERT INTO shutdown_events (run_id, reason, signal_name) VALUES (?, ?, ?)",
                (run_id, reason, signal_name),
            )
