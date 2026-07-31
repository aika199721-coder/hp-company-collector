"""Fully offline end-to-end execution of every default search provider."""

from pathlib import Path
from typing import ClassVar

from search.audit import SearchProviderAuditRepository
from search.manager import SearchManager
from search.providers.bing_rss import BingRSSProvider
from search.providers.brave import BraveSearchProvider
from search.providers.duckduckgo import DuckDuckGoHtmlProvider
from search.providers.mojeek import MojeekProvider
from storage.sqlite import Database

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


class FakeResponse:
    """Requests-compatible response backed only by repository fixtures."""

    def __init__(self, fixture: str, url: str) -> None:
        self.content = (SAMPLES / fixture).read_bytes()
        self.status_code = 200
        self.url = url

    def raise_for_status(self) -> None:
        return None


class RoutingFakeHttp:
    """Route provider endpoints to deterministic local HTML or XML."""

    fixtures: ClassVar[dict[str, str]] = {
        "www.bing.com": "bing_rss.xml",
        "html.duckduckgo.com": "duckduckgo_results.html",
        "search.brave.com": "brave_results.html",
        "www.mojeek.com": "mojeek_results.html",
    }

    def __init__(self) -> None:
        self.hosts: list[str] = []

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        host = next(host for host in self.fixtures if host in url)
        self.hosts.append(host)
        assert kwargs["headers"] == {"User-Agent": "hp-company-collector/0.10"}
        return FakeResponse(self.fixtures[host], url)


def test_all_default_providers_execute_and_are_audited(tmp_path: Path) -> None:
    database = Database(tmp_path / "provider-e2e.sqlite3")
    database.initialize()
    http = RoutingFakeHttp()
    providers = [
        BingRSSProvider(http),
        DuckDuckGoHtmlProvider(http),
        BraveSearchProvider(http),
        MojeekProvider(http),
    ]
    manager = SearchManager(
        providers,
        priorities={
            "bing_rss": 10,
            "duckduckgo_html": 20,
            "brave_search": 30,
            "mojeek": 40,
        },
        auditor=SearchProviderAuditRepository(database),
    )
    manager.set_run_id("offline-provider-e2e")

    results = manager.search("那覇市 美容室", 20)

    assert set(http.hosts) == set(http.fixtures)
    assert results
    with database.connect() as connection:
        audits = connection.execute(
            """SELECT provider, failure_type FROM search_provider_audit
               WHERE run_id = ? ORDER BY id""",
            ("offline-provider-e2e",),
        ).fetchall()
    assert [row["provider"] for row in audits] == [provider.name for provider in providers]
    assert all(row["failure_type"] is None for row in audits)
