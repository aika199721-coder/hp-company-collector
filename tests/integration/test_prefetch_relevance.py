"""Search relevance is persisted and rejected URLs are never fetched."""

from datetime import UTC, datetime
from pathlib import Path

from openpyxl import load_workbook

from live.report import LiveReportService
from pipeline.coordinator import PipelineCoordinator
from pipeline.models import PipelineLimits, ProcessingResult, ProcessingStatus, SearchCondition
from search.providers.base import SearchResult
from search.query_builder import QueryBuilder
from search.relevance import SearchResultClassifier
from storage.pipeline import PipelineRepository
from storage.progress import ProgressStore
from storage.sqlite import Database


class FakeSearchManager:
    """Return one tourism result and one relevant salon result."""

    def search(self, query: str, limit: int) -> list[SearchResult]:
        return [
            SearchResult("沖縄観光", "https://travel.example/article", "那覇市の観光", "fake", 1),
            SearchResult("那覇市 美容室", "https://salon.example.jp/", "美容院公式", "fake", 2),
        ]


class RecordingProcessor:
    """Record only candidates that pass pre-fetch filtering."""

    def __init__(self, progress: ProgressStore) -> None:
        self.progress = progress
        self.urls: list[str] = []

    def process(self, context) -> ProcessingResult:
        self.urls.append(context.candidate.url)
        self.progress.complete(context.progress_id)
        now = datetime.now(UTC)
        return ProcessingResult(
            context.condition,
            context.candidate,
            None,
            None,
            None,
            ProcessingStatus.SUCCESS,
            None,
            None,
            now,
            now,
        )


def test_low_relevance_is_saved_before_fetch(tmp_path: Path) -> None:
    database = Database(tmp_path / "collector.sqlite3")
    database.initialize()
    progress = ProgressStore(database)
    repository = PipelineRepository(database)
    processor = RecordingProcessor(progress)
    synonyms = {"美容室": ("美容室", "美容院", "ヘアサロン")}
    coordinator = PipelineCoordinator(
        QueryBuilder(synonyms),
        FakeSearchManager(),
        repository,
        progress,
        processor,
        limits=PipelineLimits(3, 20, False),
        result_classifier=SearchResultClassifier(synonyms),
        max_queries=1,
    )

    summary = coordinator.run(SearchCondition("沖縄県", "那覇市", "美容室", 3))

    assert processor.urls == ["https://salon.example.jp/"]
    assert summary.excluded_count == 1
    with database.connect() as connection:
        page = connection.execute(
            "SELECT processing_status, fetch_error FROM pages WHERE url = ?",
            ("https://travel.example/article",),
        ).fetchone()
        error_count = connection.execute(
            """SELECT COUNT(*) FROM processing_errors
               WHERE page_id = (SELECT id FROM pages WHERE url = ?)""",
            ("https://travel.example/article",),
        ).fetchone()[0]
    assert tuple(page) == ("excluded", "prefetch_tourism")
    assert error_count == 0

    report = tmp_path / "live.xlsx"
    LiveReportService(database).export(report, tmp_path / "review.csv")
    excluded = load_workbook(report)["除外"]
    values = [cell.value for cell in excluded[2]]
    assert values[:6] == [
        "https://travel.example/article",
        "那覇市 美容室",
        "fake",
        1,
        "沖縄観光",
        "prefetch_tourism",
    ]
