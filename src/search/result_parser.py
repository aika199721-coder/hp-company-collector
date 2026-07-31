"""Parsers that normalize provider response payloads."""

from __future__ import annotations

from xml.etree import ElementTree

from search.providers.base import SearchProviderError, SearchResult


def parse_bing_rss(content: bytes, limit: int) -> list[SearchResult]:
    """Parse a Bing RSS response without resolving external resources."""
    if limit < 1:
        raise ValueError("limit must be positive")
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise SearchProviderError("Bing RSS contained a prohibited XML declaration")
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise SearchProviderError("Bing RSS returned malformed XML") from exc

    results: list[SearchResult] = []
    for item in root.findall("./channel/item"):
        title = _text(item, "title")
        url = _text(item, "link")
        if not title or not url:
            continue
        results.append(
            SearchResult(
                title=title,
                url=url,
                snippet=_text(item, "description"),
                provider="bing_rss",
                rank=len(results) + 1,
            )
        )
        if len(results) == limit:
            break
    return results


def _text(element: ElementTree.Element, tag: str) -> str:
    value = element.findtext(tag)
    return value.strip() if value else ""
