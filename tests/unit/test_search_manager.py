"""SearchManager unit tests with in-memory fake providers."""

import logging

import pytest

from search.manager import SearchManager
from search.providers.base import SearchProvider, SearchProviderError, SearchResult


class FakeProvider(SearchProvider):
    """Deterministic provider with no network behavior."""

    def __init__(
        self,
        name: str,
        results: list[SearchResult] | None = None,
        error: SearchProviderError | None = None,
    ) -> None:
        self._name = name
        self.results = results or []
        self.error = error
        self.limits: list[int] = []

    @property
    def name(self) -> str:
        """Return the fake identifier."""
        return self._name

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Return configured values or raise a configured provider failure."""
        self.limits.append(limit)
        if self.error is not None:
            raise self.error
        return self.results[:limit]


def result(url: str, provider: str = "fake") -> SearchResult:
    """Build a compact normalized result fixture."""
    return SearchResult(url, url, "", provider, 1)


def test_merges_in_order_deduplicates_and_enforces_global_limit() -> None:
    first = FakeProvider("first", [result("https://EXAMPLE.jp/path/"), result("ftp://bad")])
    second = FakeProvider(
        "second",
        [result("https://example.jp/path#company"), result("https://second.example.jp/")],
    )

    results = SearchManager([first, second]).search("query", limit=2)

    assert [item.url for item in results] == [
        "https://EXAMPLE.jp/path/",
        "https://second.example.jp/",
    ]
    assert first.limits == [2]
    assert second.limits == [2]


def test_provider_failure_is_logged_and_next_provider_runs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    failed = FakeProvider("failed", error=SearchProviderError("offline"))
    healthy = FakeProvider("healthy", [result("https://healthy.example.jp/")])
    logger = logging.getLogger("test.search.manager")

    with caplog.at_level(logging.WARNING, logger=logger.name):
        results = SearchManager([failed, healthy], logger).search("query", 5)

    assert len(results) == 1
    assert "provider failed failed" in caplog.text


def test_rejects_invalid_construction_and_search_arguments() -> None:
    with pytest.raises(ValueError, match="at least one"):
        SearchManager([])
    duplicate = FakeProvider("same")
    with pytest.raises(ValueError, match="unique"):
        SearchManager([duplicate, duplicate])

    manager = SearchManager([FakeProvider("one")])
    with pytest.raises(ValueError, match="query"):
        manager.search(" ", 1)
    with pytest.raises(ValueError, match="limit"):
        manager.search("query", 0)
