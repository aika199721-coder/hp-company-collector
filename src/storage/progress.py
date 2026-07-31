"""Persistent work progress and resume operations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from storage.sqlite import Database


class ProgressStatus(StrEnum):
    """Valid lifecycle states for a resumable task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ProgressItem:
    """Immutable view of one persisted task."""

    id: int
    task_key: str
    payload: dict[str, Any]
    status: ProgressStatus
    cursor: str | None
    attempts: int
    last_error: str | None
    available_at: str | None


class ProgressStore:
    """Persist task state and provide deterministic resume behavior."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def enqueue(self, task_key: str, payload: dict[str, Any] | None = None) -> int:
        """Create a pending task, returning the existing ID for duplicate keys."""
        if not task_key.strip():
            raise ValueError("task_key must not be empty")
        serialized = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        with self.database.connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO progress(task_key, payload) VALUES (?, ?)",
                (task_key, serialized),
            )
            row = connection.execute(
                "SELECT id FROM progress WHERE task_key = ?", (task_key,)
            ).fetchone()
        assert row is not None
        return int(row["id"])

    def claim_next(self) -> ProgressItem | None:
        """Atomically claim the oldest pending task."""
        with self.database.connect() as connection:
            try:
                row = connection.execute(
                    """
                    UPDATE progress
                    SET status = 'running', attempts = attempts + 1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = (
                        SELECT id FROM progress
                        WHERE status = 'pending'
                          AND (available_at IS NULL OR available_at <= CURRENT_TIMESTAMP)
                        ORDER BY id LIMIT 1
                    )
                    RETURNING *
                    """
                ).fetchone()
            except sqlite3.OperationalError as exc:
                raise RuntimeError("SQLite 3.35 or newer is required") from exc
        return _to_item(row) if row is not None else None

    def save_cursor(self, task_id: int, cursor: str) -> None:
        """Persist a task checkpoint while it is running."""
        self._update_running(task_id, "cursor = ?", (cursor,))

    def complete(self, task_id: int) -> None:
        """Mark a running task completed and clear its previous error."""
        self._update_running(task_id, "status = 'completed', last_error = NULL", ())

    def fail(self, task_id: int, error: str) -> None:
        """Mark a running task failed with a bounded diagnostic message."""
        self._update_running(task_id, "status = 'failed', last_error = ?", (error[:2000],))

    def retry(self, task_id: int, available_at: str, error: str) -> None:
        """Return a retryable running task to pending after a UTC timestamp."""
        self._update_running(
            task_id,
            "status = 'pending', available_at = ?, last_error = ?",
            (available_at, error[:2000]),
        )

    def resume_interrupted(self) -> int:
        """Return tasks left running by an interrupted process to pending."""
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE progress
                SET status = 'pending', updated_at = CURRENT_TIMESTAMP
                WHERE status = 'running'
                """
            )
            return cursor.rowcount

    def reset_retries(self) -> int:
        """Make delayed pending tasks immediately claimable."""
        with self._database.connect() as connection:
            cursor = connection.execute(
                """UPDATE progress SET available_at = NULL
                   WHERE status = 'pending' AND available_at IS NOT NULL"""
            )
            connection.execute("DELETE FROM domain_pauses")
            return cursor.rowcount

    def get(self, task_id: int) -> ProgressItem | None:
        """Return a task by ID."""
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM progress WHERE id = ?", (task_id,)).fetchone()
        return _to_item(row) if row is not None else None

    def _update_running(self, task_id: int, assignments: str, parameters: tuple[Any, ...]) -> None:
        with self.database.connect() as connection:
            cursor = connection.execute(
                f"UPDATE progress SET {assignments}, updated_at = CURRENT_TIMESTAMP "
                "WHERE id = ? AND status = 'running'",
                (*parameters, task_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Task {task_id} is not running")


def _to_item(row: sqlite3.Row) -> ProgressItem:
    return ProgressItem(
        id=int(row["id"]),
        task_key=str(row["task_key"]),
        payload=json.loads(row["payload"]),
        status=ProgressStatus(row["status"]),
        cursor=row["cursor"],
        attempts=int(row["attempts"]),
        last_error=row["last_error"],
        available_at=row["available_at"],
    )
