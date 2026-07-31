"""Ordered provider fallback, scoring, and cross-provider URL de-duplication."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from urllib.parse import SplitResult, urlsplit, urlunsplit

from search.providers.base import SearchProvider, SearchProviderError, SearchResult


class ProviderChain:
    """Merge providers by configured priority, rank, and query-term evidence."""

    def __init__(
        self,
        providers: list[SearchProvider],
        priorities: dict[str, int] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if not providers:
            raise ValueError("at least one search provider is required")
        names = [provider.name for provider in providers]
        if len(names) != len(set(names)):
            raise ValueError("provider names must be unique")
        self._providers = tuple(providers)
        self._priorities = priorities or {
            provider.name: index * 10 for index, provider in enumerate(providers, 1)
        }
        self._logger = logger or logging.getLogger(__name__)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Run every available provider and retain the strongest normalized URL."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be positive")
        selected: dict[str, SearchResult] = {}
        for provider in self._providers:
            try:
                results = provider.search(query, limit)
            except SearchProviderError as exc:
                self._logger.warning("search provider %s failed: %s", provider.name, exc)
                continue
            for result in results:
                normalized = normalize_search_url(result.url)
                if not normalized:
                    continue
                scored = self._score(query, result)
                current = selected.get(normalized)
                if current is None or scored.chain_score > current.chain_score:
                    selected[normalized] = scored
        ordered = sorted(
            selected.values(),
            key=lambda item: (-item.chain_score, item.provider, item.rank, item.url),
        )
        return ordered[:limit]

    def _score(self, query: str, result: SearchResult) -> SearchResult:
        match = query_match_rate(query, result)
        priority = self._priorities.get(result.provider, 999)
        provider_points = max(0.0, 100.0 - float(priority))
        rank_points = max(0.0, 21.0 - float(result.rank))
        total = match * 100.0 + provider_points * 0.3 + rank_points
        return replace(result, match_score=round(match, 4), chain_score=round(total, 4))


def query_match_rate(query: str, result: SearchResult) -> float:
    """Return the fraction of meaningful query terms present in result evidence."""
    terms = tuple(
        dict.fromkeys(
            term.lower()
            for term in re.findall(r"[^\s\"]+", query)
            if term and not term.startswith("site:") and term != "公式"
        )
    )
    if not terms:
        return 0.0
    evidence = " ".join((result.title, result.snippet, result.url)).lower()
    return sum(term in evidence for term in terms) / len(terms)


def normalize_search_url(url: str) -> str:
    """Normalize HTTP(S) URLs for de-duplication across providers."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    scheme = parts.scheme.lower()
    hostname = parts.hostname.lower()
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    return urlunsplit(SplitResult(scheme, netloc, parts.path.rstrip("/") or "/", parts.query, ""))
