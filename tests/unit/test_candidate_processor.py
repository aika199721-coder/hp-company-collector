"""Phase 7 Step 2 CandidateProcessor state tests with fakes."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from crawler.result import FetchResult
from pipeline.models import CandidateUrl, ProcessingContext, ProcessingStatus, SearchCondition
from pipeline.processor import CandidateProcessor
from storage.pipeline import PipelineRepository
from storage.progress import ProgressStore
from storage.sqlite import Database


class FakeFetcher:
    """Return one configured transport result."""

    def __init__(self, result: FetchResult) -> None:
        self.result = result
        self.calls = 0

    def fetch(self, url: str) -> FetchResult:
        """Return a raw fake response."""
        self.calls += 1
        return self.result


class RaisingFacade:
    """Raise a configured extraction/scoring error."""

    def extract(self, html: str, source_url: str) -> None:
        """Raise an extraction error."""
        raise ValueError("extract fixture error")


@pytest.fixture
def context(tmp_path: Path) -> tuple[ProcessingContext, PipelineRepository, ProgressStore]:
    """Create a claimed temporary pipeline task."""
    database = Database(tmp_path / "processor.sqlite3")
    database.initialize()
    repository = PipelineRepository(database)
    progress = ProgressStore(database)
    condition = SearchCondition("東京都", "千代田区", "建設業", 1)
    condition_id = repository.create_condition(condition)
    candidate = CandidateUrl("https://fixture.invalid/", "query", "fake", 1, "title", "")
    result_id = repository.record_candidate(condition_id, candidate)
    progress.enqueue(
        candidate.url,
        {
            "candidate": candidate.to_dict(),
            "condition_id": condition_id,
            "search_result_id": result_id,
        },
    )
    item = progress.claim_next()
    assert item is not None
    pipeline_context = ProcessingContext(
        condition, candidate, item.id, condition_id, result_id
    )
    return pipeline_context, repository, progress


def test_robots_denial_is_dedicated_non_error_state(context: tuple) -> None:
    pipeline_context, repository, progress = context
    fetcher = FakeFetcher(
        FetchResult(
            pipeline_context.candidate.url,
            pipeline_context.candidate.url,
            None,
            error="robots_denied",
        )
    )
    processor = CandidateProcessor(fetcher, RaisingFacade(), None, repository, progress)

    result = processor.process(pipeline_context)

    assert result.status is ProcessingStatus.ROBOTS_DENIED
    assert result.error_type is None
    assert progress.get(pipeline_context.progress_id).status.value == "completed"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (403, ProcessingStatus.HTTP_403),
        (404, ProcessingStatus.HTTP_404),
        (503, ProcessingStatus.HTTP_503),
    ],
)
def test_http_statuses_are_distinct(
    context: tuple, status_code: int, expected: ProcessingStatus
) -> None:
    pipeline_context, repository, progress = context
    fetch = FetchResult(pipeline_context.candidate.url, pipeline_context.candidate.url, status_code)
    processor = CandidateProcessor(
        FakeFetcher(fetch), RaisingFacade(), None, repository, progress
    )
    result = processor.process(pipeline_context)

    assert result.status is expected


def test_429_sets_retry_and_domain_pause(context: tuple) -> None:
    pipeline_context, repository, progress = context
    fetch = FetchResult(
        pipeline_context.candidate.url,
        pipeline_context.candidate.url,
        429,
        {"retry-after": "120"},
    )
    now = datetime(2026, 1, 1, tzinfo=UTC)
    processor = CandidateProcessor(
        FakeFetcher(fetch),
        RaisingFacade(),
        None,
        repository,
        progress,
        clock=lambda: now,
    )

    result = processor.process(pipeline_context)

    assert result.status is ProcessingStatus.HTTP_429
    assert progress.get(pipeline_context.progress_id).status.value == "pending"
    assert repository.domain_pause_until(pipeline_context.candidate.url) is not None
