"""Offline provider audit and classified HTML failure regression tests."""

from pathlib import Path

import pytest
import requests

from search.audit import SearchProviderAuditRepository
from search.provider_chain import ProviderChain
from search.providers.base import SearchProvider, SearchProviderError, SearchResult
from search.providers.duckduckgo import DuckDuckGoHtmlProvider
from storage.sqlite import Database


class FakeProvider(SearchProvider):
    """Return or fail deterministically without external communication."""

    def __init__(self, name: str, error: SearchProviderError | None = None) -> None:
        self._name = name
        self._error = error
        self.called = 0

    @property
    def name(self) -> str:
        return self._name

    def search(self, query: str, limit: int) -> list[SearchResult]:
        self.called += 1
        if self._error:
            raise self._error
        return [SearchResult("那覇市 美容室", f"https://{self.name}.example/", "", self.name, 1)]


def test_failure_is_audited_and_later_providers_continue(tmp_path: Path) -> None:
    database = Database(tmp_path / "audit.db")
    database.initialize()
    failed = FakeProvider(
        "bing_rss", SearchProviderError("blocked", failure_type="http_403", http_status=403)
    )
    later = FakeProvider("duckduckgo_html")
    chain = ProviderChain(
        [failed, later], auditor=SearchProviderAuditRepository(database)
    )
    chain.set_run_id("run-a")

    assert len(chain.search("那覇市 美容室", 10)) == 1
    assert failed.called == later.called == 1
    assert len(chain.search("那覇市 美容院", 10)) == 1
    assert failed.called == 1
    assert later.called == 2
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT provider, enabled, http_status, result_count, accepted_count, failure_type "
            "FROM search_provider_audit ORDER BY id"
        ).fetchall()
    assert tuple(rows[0]) == ("bing_rss", 1, 403, 0, 0, "http_403")
    assert tuple(rows[1]) == ("duckduckgo_html", 1, None, 1, 1, None)
    assert rows[2]["failure_type"] == "provider_stopped"


class FakeHtmlResponse:
    """Minimal requests-compatible HTML response."""

    def __init__(self, status: int, content: bytes) -> None:
        self.status_code = status
        self.content = content
        self.url = "https://search.example/final"

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            response = requests.Response()
            response.status_code = self.status_code
            response.url = self.url
            raise requests.HTTPError(response=response)


class FakeHtmlClient:
    def __init__(self, response: FakeHtmlResponse | Exception) -> None:
        self.response = response

    def get(self, url: str, **kwargs):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.mark.parametrize(
    ("response", "failure"),
    [
        (FakeHtmlResponse(403, b"blocked"), "http_403"),
        (FakeHtmlResponse(429, b"limited"), "http_429"),
        (FakeHtmlResponse(200, b"<html>changed</html>"), "parser_mismatch"),
        (requests.Timeout("slow"), "timeout"),
    ],
)
def test_html_provider_classifies_failures(response: object, failure: str) -> None:
    provider = DuckDuckGoHtmlProvider(FakeHtmlClient(response))

    with pytest.raises(SearchProviderError) as raised:
        provider.search("那覇市 美容室", 10)

    assert raised.value.failure_type == failure


def test_html_provider_distinguishes_explicit_zero_results() -> None:
    provider = DuckDuckGoHtmlProvider(
        FakeHtmlClient(FakeHtmlResponse(200, b"<html>No results found</html>"))
    )

    assert provider.search("那覇市 美容室", 10) == []
