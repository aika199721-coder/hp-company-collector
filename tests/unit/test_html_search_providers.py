"""Offline HTML-provider parsing tests with injected clients."""

from pathlib import Path

import pytest

from search.provider_chain import ProviderChain
from search.providers.brave import BraveSearchProvider
from search.providers.duckduckgo import DuckDuckGoHtmlProvider
from search.providers.mojeek import MojeekProvider

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


class FakeResponse:
    def __init__(self, name: str) -> None:
        self.content = (SAMPLES / name).read_bytes()
        self.status_code = 200
        self.url = "https://search.example/results"

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(self, fixture: str) -> None:
        self.fixture = fixture
        self.calls: list[tuple[str, dict[str, str], float]] = []

    def get(self, url: str, **kwargs):
        params = kwargs["params"]
        timeout = kwargs["timeout"]
        self.calls.append((url, params, timeout))
        assert kwargs["headers"]["User-Agent"] == "hp-company-collector/0.10"
        return FakeResponse(self.fixture)


@pytest.mark.parametrize(
    ("provider_type", "fixture", "expected"),
    [
        (DuckDuckGoHtmlProvider, "duckduckgo_results.html", ["salon-a", "salon-b"]),
        (BraveSearchProvider, "brave_results.html", ["salon-c", "salon-a"]),
        (MojeekProvider, "mojeek_results.html", ["salon-d", "salon-e"]),
    ],
)
def test_html_provider_parses_ranked_urls(provider_type, fixture: str, expected: list[str]) -> None:
    client = FakeClient(fixture)

    results = provider_type(client=client).search("那覇市 美容室", 10)

    assert [
        part for result, part in zip(results, expected, strict=True) if part in result.url
    ] == expected
    assert [result.rank for result in results] == [1, 2]
    assert len(client.calls) == 1


def test_beauty_query_chain_returns_at_least_five_official_candidates() -> None:
    """Reproduce the required provider diversity without accessing real search sites."""
    providers = [
        DuckDuckGoHtmlProvider(FakeClient("duckduckgo_results.html")),
        BraveSearchProvider(FakeClient("brave_results.html")),
        MojeekProvider(FakeClient("mojeek_results.html")),
    ]
    chain = ProviderChain(
        providers,
        {"duckduckgo_html": 20, "brave_search": 30, "mojeek": 40},
    )

    results = chain.search("那覇市 美容室", 10)

    assert len(results) >= 5
    assert all(result.match_score > 0 for result in results)
