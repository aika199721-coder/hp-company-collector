"""Yahoo! JAPAN HTML search provider."""

from __future__ import annotations

from bs4 import BeautifulSoup

from search.providers.base import SearchResult
from search.providers.html_base import HtmlSearchProvider


class YahooJapanHtmlProvider(HtmlSearchProvider):
    """Parse Yahoo! JAPAN web-search result cards."""

    endpoint = "https://search.yahoo.co.jp/search"

    @property
    def name(self) -> str:
        """Return the provider configuration identifier."""
        return "yahoo_japan_html"

    def _params(self, query: str) -> dict[str, str]:
        return {"p": query}

    def parse(self, content: bytes, limit: int) -> list[SearchResult]:
        """Extract URL, title, and description from Yahoo result cards."""
        soup = BeautifulSoup(content, "html.parser")
        results: list[SearchResult] = []
        for node in soup.select(".sw-CardBase"):
            link = node.select_one("h3 a[href]")
            if link is None:
                continue
            url = str(link.get("href", ""))
            if not url.startswith(("http://", "https://")):
                continue
            snippet = node.select_one(".sw-Card__summary, p")
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
