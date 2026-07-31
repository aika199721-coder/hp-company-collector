"""SQLite progress and resume integration tests."""

from pathlib import Path

import pytest

from storage.progress import ProgressStatus, ProgressStore
from storage.sqlite import SCHEMA_VERSION, Database


@pytest.fixture
def store(tmp_path: Path) -> ProgressStore:
    database = Database(tmp_path / "nested" / "collector.sqlite3")
    database.initialize()
    return ProgressStore(database)


def test_database_initialization_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "collector.sqlite3")
    database.initialize()
    database.initialize()

    with database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_task_lifecycle_and_duplicate_enqueue(store: ProgressStore) -> None:
    task_id = store.enqueue("tokyo:chiyoda:restaurant", {"市区町村": "千代田区"})
    assert store.enqueue("tokyo:chiyoda:restaurant", {"ignored": True}) == task_id

    task = store.claim_next()
    assert task is not None
    assert task.status is ProgressStatus.RUNNING
    assert task.attempts == 1
    assert task.payload == {"市区町村": "千代田区"}

    store.save_cursor(task.id, "page:2")
    store.complete(task.id)
    completed = store.get(task.id)
    assert completed is not None
    assert completed.status is ProgressStatus.COMPLETED
    assert completed.cursor == "page:2"
    assert store.claim_next() is None


def test_resume_recovers_only_interrupted_tasks(store: ProgressStore) -> None:
    first_id = store.enqueue("first")
    second_id = store.enqueue("second")
    first = store.claim_next()
    second = store.claim_next()
    assert first is not None and second is not None
    store.fail(second_id, "temporary failure")

    assert store.resume_interrupted() == 1
    resumed = store.claim_next()
    assert resumed is not None
    assert resumed.id == first_id
    assert resumed.attempts == 2
    failed = store.get(second_id)
    assert failed is not None
    assert failed.status is ProgressStatus.FAILED


def test_invalid_transition_is_rejected(store: ProgressStore) -> None:
    task_id = store.enqueue("pending")
    with pytest.raises(ValueError, match="is not running"):
        store.complete(task_id)
