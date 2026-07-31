"""DuckDuckGo HTML search provider."""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup

from search.providers.base import SearchResult
from search.providers.html_base import HtmlSearchProvider


class DuckDuckGoHtmlProvider(HtmlSearchProvider):
    """Parse the non-JavaScript DuckDuckGo HTML result page."""

    endpoint = "https://html.duckduckgo.com/html/"

    @property
    def name(self) -> str:
        return "duckduckgo_html"

    def parse(self, content: bytes, limit: int) -> list[SearchResult]:
        soup = BeautifulSoup(content, "html.parser")
        results: list[SearchResult] = []
        for node in soup.select(".result"):
            link = node.select_one("a.result__a")
            if link is None or not link.get("href"):
                continue
            snippet = node.select_one(".result__snippet")
            results.append(
                SearchResult(
                    link.get_text(" ", strip=True),
                    _destination(str(link["href"])),
                    snippet.get_text(" ", strip=True) if snippet else "",
                    self.name,
                    len(results) + 1,
                )
            )
            if len(results) >= limit:
                break
        return results


def _destination(url: str) -> str:
    absolute = f"https:{url}" if url.startswith("//") else url
    values = parse_qs(urlsplit(absolute).query).get("uddg")
    return unquote(values[0]) if values else absolute
