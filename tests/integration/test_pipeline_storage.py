"""Phase 7 Step 4 SQLite pipeline schema and repository tests."""

from pathlib import Path

from pipeline.models import CandidateUrl, SearchCondition
from storage.pipeline import PipelineRepository
from storage.sqlite import SCHEMA_VERSION, Database


def test_schema_migrates_and_preserves_url_history_across_conditions(tmp_path: Path) -> None:
    database = Database(tmp_path / "pipeline.sqlite3")
    database.initialize()
    repository = PipelineRepository(database)
    first = repository.create_condition(SearchCondition("東京都", "千代田区", "建設業", 3))
    second = repository.create_condition(SearchCondition("大阪府", "大阪市", "建設業", 3))
    candidate = CandidateUrl("https://same.example/", "query", "fake", 1, "同じ", "snippet")

    repository.record_candidate(first, candidate)
    repository.record_candidate(second, candidate)

    with database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("SELECT COUNT(*) FROM search_results").fetchone()[0] == 2
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {
        "search_conditions",
        "search_queries",
        "search_results",
        "pages",
        "companies",
        "phones",
        "addresses",
        "scoring_results",
        "processing_errors",
        "progress",
    } <= tables
