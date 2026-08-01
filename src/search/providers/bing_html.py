"""Bing HTML search provider restored as an RSS-independent route."""

from __future__ import annotations

from bs4 import BeautifulSoup

from search.providers.base import SearchResult
from search.providers.html_base import HtmlSearchProvider


class BingHtmlProvider(HtmlSearchProvider):
    """Parse Bing's established ``li.b_algo`` result markup."""

    endpoint = "https://www.bing.com/search"

    @property
    def name(self) -> str:
        """Return the provider configuration identifier."""
        return "bing_html"

    def parse(self, content: bytes, limit: int) -> list[SearchResult]:
        """Extract URL, title, and description from Bing HTML results."""
        soup = BeautifulSoup(content, "html.parser")
        results: list[SearchResult] = []
        for node in soup.select("li.b_algo"):
            link = node.select_one("h2 a[href]")
            if link is None:
                continue
            url = str(link.get("href", ""))
            if not url.startswith(("http://", "https://")):
                continue
            snippet = node.select_one(".b_caption p, p")
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
