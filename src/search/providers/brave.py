"""Brave Search HTML provider without a paid API."""

from __future__ import annotations

from bs4 import BeautifulSoup

from search.providers.base import SearchResult
from search.providers.html_base import HtmlSearchProvider


class BraveSearchProvider(HtmlSearchProvider):
    """Parse public Brave Search HTML result cards."""

    endpoint = "https://search.brave.com/search"

    @property
    def name(self) -> str:
        return "brave_search"

    def parse(self, content: bytes, limit: int) -> list[SearchResult]:
        soup = BeautifulSoup(content, "html.parser")
        results: list[SearchResult] = []
        for node in soup.select(".snippet"):
            link = node.select_one("a[href]")
            title = node.select_one(".title") or link
            if link is None or title is None:
                continue
            url = str(link.get("href", ""))
            if not url.startswith(("http://", "https://")):
                continue
            snippet = node.select_one(".description, .snippet-description")
            results.append(
                SearchResult(
                    title.get_text(" ", strip=True),
                    url,
                    snippet.get_text(" ", strip=True) if snippet else "",
                    self.name,
                    len(results) + 1,
                )
            )
            if len(results) >= limit:
                break
        return results
