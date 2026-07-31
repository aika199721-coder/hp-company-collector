"""Mojeek HTML search provider."""

from __future__ import annotations

from bs4 import BeautifulSoup

from search.providers.base import SearchResult
from search.providers.html_base import HtmlSearchProvider


class MojeekProvider(HtmlSearchProvider):
    """Parse Mojeek standard result list markup."""

    endpoint = "https://www.mojeek.com/search"

    @property
    def name(self) -> str:
        return "mojeek"

    def parse(self, content: bytes, limit: int) -> list[SearchResult]:
        soup = BeautifulSoup(content, "html.parser")
        results: list[SearchResult] = []
        for node in soup.select("ul.results-standard > li, .results-standard .result"):
            link = node.select_one("h2 a[href]")
            if link is None:
                continue
            url = str(link.get("href", ""))
            if not url.startswith(("http://", "https://")):
                continue
            snippet = node.select_one(".s, .result-desc, p")
            results.append(
                SearchResult(
                    link.get_text(" ", strip=True),
                    url,
                    snippet.get_text(" ", strip=True) if snippet else "",
                    self.name,
                    len(results) + 1,
                )
            )
            if len(results) >= limit:
                break
        return results
