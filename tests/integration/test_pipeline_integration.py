"""Phase 7 Steps 2, 3, 5, and 6 offline pipeline integration tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
import requests
import yaml

from crawler.fetcher import Fetcher
from crawler.result import FetchResult
from extractor.facade import ExtractorFacade
from pipeline.coordinator import PipelineCoordinator
from pipeline.models import CandidateUrl, PipelineLimits, ProcessingStatus, SearchCondition
from pipeline.processor import CandidateProcessor
from scoring.facade import ScoringFacade
from search.manager import SearchManager
from search.providers.base import SearchProvider, SearchResult
from search.query_builder import QueryBuilder
from storage.pipeline import PipelineRepository
from storage.progress import ProgressStore
from storage.sqlite import Database

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "tests/html_samples"


class FakeProvider(SearchProvider):
    """Return deterministic search results without network access."""

    def __init__(self, urls: list[str]) -> None:
        self.urls = urls

    @property
    def name(self) -> str:
        """Return the fake provider ID."""
        return "fake"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Return at most the requested number of fake discoveries."""
        return [
            SearchResult(f"title-{rank}", url, "snippet", self.name, rank)
            for rank, url in enumerate(self.urls[:limit], 1)
        ]


class FakeResponse:
    """Minimal requests-compatible response."""

    def __init__(self, url: str, status: int, content: bytes = b"") -> None:
        self.url = url
        self.status_code = status
        self.content = content
        self.headers: Mapping[str, str] = {}
        self.encoding = "utf-8"


class FakeHttpClient:
    """Resolve URL-specific fake responses or exceptions."""

    def __init__(self, outcomes: Mapping[str, FakeResponse | requests.RequestException]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    def get(
        self,
        url: str,
        *,
        timeout: float,
        allow_redirects: bool,
        headers: Mapping[str, str],
    ) -> FakeResponse:
        """Return fake transport data."""
        self.calls.append(url)
        outcome = self.outcomes[url]
        if isinstance(outcome, requests.RequestException):
            raise outcome
        return outcome


class FakeRobots:
    """Deny configured URLs and allow all others."""

    def __init__(self, denied: set[str] | None = None) -> None:
        self.denied = denied or set()

    def can_fetch(self, url: str) -> bool:
        """Return the fixture policy decision."""
        return url not in self.denied


class FakeLimiter:
    """Record calls without sleeping."""

    def wait(self, url: str, delay_seconds: float | None = None) -> None:
        """Perform no real wait."""


class FakePlaywright:
    """Injected browser mock that is never allowed to access a site."""

    def fetch(self, url: str, timeout_seconds: float) -> FetchResult:
        """Return a fake browser response."""
        return FetchResult(url, url, 403, from_playwright=True)


class RaisingExtractor:
    """Extraction facade fake that always fails."""

    def extract(self, html: str, source_url: str) -> Any:
        """Raise a deterministic extraction exception."""
        raise ValueError("synthetic extraction failure")


class RaisingScorer:
    """Scoring facade fake that always fails."""

    def score(self, extraction: Any, url: str, context: Any, html: str) -> Any:
        """Raise a deterministic scoring exception."""
        raise ValueError("synthetic scoring failure")


def html(name: str) -> bytes:
    """Read one synthetic HTML fixture as bytes."""
    return (SAMPLES / name).read_bytes()


def build_pipeline(
    tmp_path: Path,
    urls: list[str],
    outcomes: Mapping[str, FakeResponse | requests.RequestException],
    *,
    denied: set[str] | None = None,
    extractor: Any = None,
    scorer: Any = None,
    pipeline_limits: PipelineLimits | None = None,
) -> tuple[PipelineCoordinator, Database, FakeHttpClient, ProgressStore, PipelineRepository]:
    """Build the complete pipeline with fake external boundaries and temporary SQLite."""
    database = Database(tmp_path / "pipeline.sqlite3")
    database.initialize()
    repository = PipelineRepository(database)
    progress = ProgressStore(database)
    client = FakeHttpClient(outcomes)
    fetcher = Fetcher(
        FakeRobots(denied),
        FakeLimiter(),
        client=client,
        playwright=FakePlaywright(),
    )
    if scorer is None:
        config = yaml.safe_load((ROOT / "config/scoring.yaml").read_text(encoding="utf-8"))
        scorer = ScoringFacade(
            config,
            exclude_domains_path=ROOT / "config/exclude_domains.txt",
        )
    processor = CandidateProcessor(
        fetcher,
        extractor or ExtractorFacade(),
        scorer,
        repository,
        progress,
        retry_delay_seconds=60,
    )
    coordinator = PipelineCoordinator(
        QueryBuilder(),
        SearchManager([FakeProvider(urls)]),
        repository,
        progress,
        processor,
        limits=pipeline_limits,
    )
    return coordinator, database, client, progress, repository


def condition(limit: int = 5, city: str = "千代田区") -> SearchCondition:
    """Return a common enabled search condition."""
    return SearchCondition("東京都", city, "建設業", limit)


def test_official_portal_and_no_phone_are_all_persisted(tmp_path: Path) -> None:
    urls = [
        "https://official.example/",
        "https://itp.ne.jp/ranking",
        "https://no-phone.example/",
    ]
    outcomes = {
        urls[0]: FakeResponse(urls[0], 200, html("scoring_official.html")),
        urls[1]: FakeResponse(urls[1], 200, html("scoring_portal.html")),
        urls[2]: FakeResponse(urls[2], 200, html("scoring_no_phone.html")),
    }
    coordinator, database, _, _, _ = build_pipeline(tmp_path, urls, outcomes)

    summary = coordinator.run(condition())

    assert summary.processed == 3
    assert ProcessingStatus.SUCCESS in summary.status_counts
    assert ProcessingStatus.EXCLUDED in summary.status_counts
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM scoring_results").fetchone()[0] == 3
        no_phone = connection.execute(
            """
            SELECT COUNT(*) FROM phones p
            JOIN companies c ON c.id = p.company_id
            JOIN pages pg ON pg.id = c.page_id
            WHERE pg.url = ?
            """,
            (urls[2],),
        ).fetchone()[0]
    assert no_phone == 0


def test_transport_states_and_one_error_do_not_stop_next_candidate(tmp_path: Path) -> None:
    urls = [
        "https://denied.example/",
        "https://missing.example/",
        "https://limited.example/",
        "https://timeout.example/",
        "https://next.example/",
    ]
    outcomes = {
        urls[1]: FakeResponse(urls[1], 404),
        urls[2]: FakeResponse(urls[2], 429),
        urls[3]: requests.Timeout("synthetic timeout"),
        urls[4]: FakeResponse(urls[4], 200, html("scoring_official.html")),
    }
    coordinator, database, _, _, repository = build_pipeline(
        tmp_path, urls, outcomes, denied={urls[0]}
    )

    summary = coordinator.run(condition())

    assert summary.status_counts[ProcessingStatus.ROBOTS_DENIED] == 1
    assert summary.status_counts[ProcessingStatus.HTTP_404] == 1
    assert summary.status_counts[ProcessingStatus.HTTP_429] == 1
    assert summary.status_counts[ProcessingStatus.TIMEOUT] == 1
    assert summary.status_counts[ProcessingStatus.SUCCESS] == 1
    assert repository.domain_pause_until(urls[2]) is not None
    with database.connect() as connection:
        retry_count = connection.execute(
            "SELECT COUNT(*) FROM progress WHERE status = 'pending' AND available_at IS NOT NULL"
        ).fetchone()[0]
    assert retry_count == 2


@pytest.mark.parametrize(
    ("extractor", "scorer", "expected"),
    [
        (RaisingExtractor(), None, ProcessingStatus.EXTRACTION_FAILED),
        (ExtractorFacade(), RaisingScorer(), ProcessingStatus.SCORING_FAILED),
    ],
)
def test_stage_exception_is_persisted(
    tmp_path: Path, extractor: Any, scorer: Any, expected: ProcessingStatus
) -> None:
    url = "https://failure.example/"
    outcomes = {url: FakeResponse(url, 200, html("scoring_official.html"))}
    coordinator, database, _, _, _ = build_pipeline(
        tmp_path, [url], outcomes, extractor=extractor, scorer=scorer
    )

    summary = coordinator.run(condition(1))

    assert summary.results[0].status is expected
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM processing_errors").fetchone()[0] == 1


def test_duplicate_url_fetches_once_but_preserves_two_search_histories(tmp_path: Path) -> None:
    url = "https://same.example/"
    outcomes = {url: FakeResponse(url, 200, html("scoring_official.html"))}
    coordinator, database, client, _, _ = build_pipeline(tmp_path, [url], outcomes)

    coordinator.run(condition(1, "千代田区"))
    coordinator.run(condition(1, "中央区"))

    assert client.calls == [url]
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM search_results").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1


def test_resume_running_and_maximum_limit(tmp_path: Path) -> None:
    urls = [f"https://resume-{index}.example/" for index in range(3)]
    outcomes = {
        url: FakeResponse(url, 200, html("scoring_official.html")) for url in urls
    }
    coordinator, _, _, progress, repository = build_pipeline(tmp_path, urls, outcomes)
    old_condition = condition(2)
    condition_id = repository.create_condition(old_condition)
    candidate = CandidateUrl(urls[0], "old query", "fake", 1, "old", "")
    result_id = repository.record_candidate(condition_id, candidate)
    task_id = progress.enqueue(
        candidate.url,
        {
            "candidate": candidate.to_dict(),
            "condition": {
                "prefecture": "東京都",
                "municipality": "千代田区",
                "industry": "建設業",
                "max_results": 2,
                "enabled": True,
            },
            "condition_id": condition_id,
            "search_result_id": result_id,
        },
    )
    claimed = progress.claim_next()
    assert claimed is not None and claimed.id == task_id

    summary = coordinator.run(condition(2))

    assert summary.processed == 2
    assert progress.get(task_id).status.value == "completed"


def test_429_pause_defers_another_url_on_the_same_domain(tmp_path: Path) -> None:
    """Persisted origin pauses prevent an immediate second request."""
    urls = ["https://limited.example/one", "https://limited.example/two"]
    outcomes = {
        urls[0]: FakeResponse(urls[0], 429),
        urls[1]: FakeResponse(urls[1], 200, html("scoring_official.html")),
    }
    coordinator, _, client, _, _ = build_pipeline(tmp_path, urls, outcomes)

    summary = coordinator.run(condition(2))

    assert client.calls == [urls[0]]
    assert summary.status_counts[ProcessingStatus.HTTP_429] == 2


def test_target_limit_counts_adopted_results_not_processed_urls(tmp_path: Path) -> None:
    """Excluded candidates do not consume the requested target count."""
    urls = [
        "https://itp.ne.jp/first",
        "https://target-one.example/",
        "https://target-two.example/",
    ]
    outcomes = {
        urls[0]: FakeResponse(urls[0], 200, html("scoring_portal.html")),
        urls[1]: FakeResponse(urls[1], 200, html("scoring_official.html")),
        urls[2]: FakeResponse(urls[2], 200, html("scoring_official.html")),
    }
    coordinator, _, client, _, _ = build_pipeline(
        tmp_path,
        urls,
        outcomes,
        pipeline_limits=PipelineLimits(500, 10, False),
    )

    summary = coordinator.run(condition(1))

    assert summary.candidate_count == 3
    assert summary.processed_count == 2
    assert summary.business_target_count == 1
    assert summary.excluded_count == 1
    assert client.calls == urls[:2]


def test_candidate_safety_limit_stops_without_target(tmp_path: Path) -> None:
    """Candidate limit prevents endless processing when every result is excluded."""
    urls = [f"https://itp.ne.jp/excluded-{index}" for index in range(4)]
    outcomes = {
        url: FakeResponse(url, 200, html("scoring_portal.html")) for url in urls
    }
    coordinator, _, client, _, _ = build_pipeline(
        tmp_path,
        urls,
        outcomes,
        pipeline_limits=PipelineLimits(500, 2, False),
    )

    summary = coordinator.run(condition(3))

    assert summary.processed_count == 2
    assert summary.business_target_count == 0
    assert summary.excluded_count == 2
    assert client.calls == urls[:2]


def test_no_phone_target_count_is_configurable(tmp_path: Path) -> None:
    """A no-phone scoring target is persisted but optionally omitted from the stop count."""
    urls = ["https://no-phone.example/", "https://target.example/"]
    outcomes = {
        urls[0]: FakeResponse(urls[0], 200, html("scoring_no_phone.html")),
        urls[1]: FakeResponse(urls[1], 200, html("scoring_official.html")),
    }
    coordinator, _, _, _, _ = build_pipeline(
        tmp_path,
        urls,
        outcomes,
        pipeline_limits=PipelineLimits(500, 10, False),
    )

    summary = coordinator.run(condition(1))

    assert summary.processed_count == 2
    assert summary.no_phone_count == 1
    assert summary.business_target_count == 1

    second_path = tmp_path / "counted"
    counted, _, counted_client, _, _ = build_pipeline(
        second_path,
        urls,
        outcomes,
        pipeline_limits=PipelineLimits(500, 10, True),
    )
    counted_summary = counted.run(condition(1))

    assert counted_summary.processed_count == 1
    assert counted_summary.business_target_count == 1
    assert counted_client.calls == [urls[0]]
