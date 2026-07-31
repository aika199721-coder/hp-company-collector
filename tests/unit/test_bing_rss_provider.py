"""Offline Bing RSS provider tests using repository fixtures only."""

from pathlib import Path

import pytest
import requests

from search.providers.base import SearchProviderError
from search.providers.bing_rss import BingRSSProvider

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


class FakeResponse:
    """Small requests-compatible response fixture."""

    def __init__(self, content: bytes, error: requests.RequestException | None = None) -> None:
        self.content = content
        self.error = error
        self.status_code = 200
        self.url = "https://www.bing.com/search"

    def raise_for_status(self) -> None:
        """Raise the configured HTTP error."""
        if self.error is not None:
            raise self.error


class FakeClient:
    """Record calls and return a local fixture without network access."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, str | int], float]] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        """Return the injected response."""
        self.calls.append((url, kwargs["params"], kwargs["timeout"]))
        assert kwargs["headers"] == {"User-Agent": "hp-company-collector/0.10"}
        assert kwargs["allow_redirects"] is True
        return self.response


def test_parses_local_rss_fixture_and_honors_limit() -> None:
    content = (SAMPLES / "bing_rss.xml").read_bytes()
    client = FakeClient(FakeResponse(content))
    provider = BingRSSProvider(client=client, timeout_seconds=3.5)

    results = provider.search("sample query", limit=1)

    assert len(results) == 1
    assert results[0].title == "株式会社サンプル 公式サイト"
    assert results[0].url == "https://sample.example.jp/"
    assert results[0].provider == "bing_rss"
    assert results[0].rank == 1
    assert client.calls == [
        (
            "https://www.bing.com/search",
            {"q": "sample query", "format": "rss", "count": 1},
            3.5,
        )
    ]


def test_skips_incomplete_items() -> None:
    content = (SAMPLES / "bing_rss.xml").read_bytes()
    provider = BingRSSProvider(client=FakeClient(FakeResponse(content)))

    assert len(provider.search("sample", limit=10)) == 2


def test_wraps_http_and_malformed_xml_errors() -> None:
    failed = FakeClient(FakeResponse(b"", requests.HTTPError("503")))
    with pytest.raises(SearchProviderError, match="returned HTTP"):
        BingRSSProvider(client=failed).search("sample", 1)

    malformed = (SAMPLES / "malformed_rss.xml").read_bytes()
    with pytest.raises(SearchProviderError, match="malformed XML"):
        BingRSSProvider(client=FakeClient(FakeResponse(malformed))).search("sample", 1)


def test_rejects_xml_entity_declarations() -> None:
    unsafe = (SAMPLES / "unsafe_rss.xml").read_bytes()

    with pytest.raises(SearchProviderError, match="prohibited XML declaration"):
        BingRSSProvider(client=FakeClient(FakeResponse(unsafe))).search("sample", 1)


@pytest.mark.parametrize(("query", "limit"), [("", 1), ("sample", 0)])
def test_rejects_invalid_search_arguments(query: str, limit: int) -> None:
    provider = BingRSSProvider(client=FakeClient(FakeResponse(b"")))

    with pytest.raises(ValueError):
        provider.search(query, limit)
