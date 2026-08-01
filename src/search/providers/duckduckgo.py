"""DuckDuckGo HTML search provider."""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

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
        for node in soup.select("div.body, .result"):
            link = node.select_one(":scope > a[href], a.result__a[href]")
            if link is None or not link.get("href"):
                continue
            title_node = link.select_one("h2")
            title = (
                title_node.get_text(" ", strip=True)
                if title_node is not None
                else link.get_text(" ", strip=True)
            )
            snippet_node = node.select_one(".result__snippet, .snippet, p")
            snippet = _snippet(link, title, snippet_node)
            results.append(
                SearchResult(
                    title,
                    _destination(str(link["href"])),
                    snippet,
                    self.name,
                    len(results) + 1,
                )
            )
            if len(results) >= limit:
                break
        return results


def _snippet(link: Tag, title: str, snippet_node: Tag | None) -> str:
    """Extract result summary text from current and legacy DuckDuckGo markup."""
    if snippet_node is not None:
        return snippet_node.get_text(" ", strip=True)
    combined = link.get_text(" ", strip=True)
    return combined.removeprefix(title).strip()


def _destination(url: str) -> str:
    absolute = f"https:{url}" if url.startswith("//") else url
    values = parse_qs(urlsplit(absolute).query).get("uddg")
    return unquote(values[0]) if values else absolute
