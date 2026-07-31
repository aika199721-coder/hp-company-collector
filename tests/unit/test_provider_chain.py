"""ProviderChain scoring, fallback, and normalized de-duplication tests."""

from search.provider_chain import ProviderChain
from search.providers.base import SearchProvider, SearchProviderError, SearchResult


class FakeProvider(SearchProvider):
    """Deterministic provider for offline chain tests."""

    def __init__(self, name: str, results: list[SearchResult], fail: bool = False) -> None:
        self._name = name
        self.results = results
        self.fail = fail

    @property
    def name(self) -> str:
        return self._name

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if self.fail:
            raise SearchProviderError("offline failure")
        return self.results[:limit]


def item(title: str, url: str, provider: str, rank: int) -> SearchResult:
    return SearchResult(title, url, "那覇市 美容室 公式", provider, rank)


def test_chain_falls_back_deduplicates_and_scores_evidence() -> None:
    providers = [
        FakeProvider("bing_rss", [], fail=True),
        FakeProvider(
            "duckduckgo_html", [item("美容室 A", "https://EXAMPLE.jp/", "duckduckgo_html", 2)]
        ),
        FakeProvider(
            "brave_search", [item("那覇市 美容室 A", "https://example.jp", "brave_search", 1)]
        ),
        FakeProvider("mojeek", [item("那覇市 美容室 B", "https://b.example.jp/", "mojeek", 1)]),
    ]
    chain = ProviderChain(
        providers, {"bing_rss": 10, "duckduckgo_html": 20, "brave_search": 30, "mojeek": 40}
    )

    results = chain.search("那覇市 美容室", 10)

    assert [result.url.lower().rstrip("/") for result in results] == [
        "https://example.jp",
        "https://b.example.jp",
    ]
    assert results[0].provider == "duckduckgo_html"
    assert results[0].match_score >= results[1].match_score
