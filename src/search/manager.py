"""Provider orchestration without crawling destination sites."""

from __future__ import annotations

import logging
from urllib.parse import SplitResult, urlsplit, urlunsplit

from search.providers.base import SearchProvider, SearchProviderError, SearchResult


class SearchManager:
    """Run providers in order and merge their normalized results."""

    def __init__(
        self,
        providers: list[SearchProvider],
        logger: logging.Logger | None = None,
    ) -> None:
        if not providers:
            raise ValueError("at least one search provider is required")
        names = [provider.name for provider in providers]
        if len(names) != len(set(names)):
            raise ValueError("provider names must be unique")
        self._providers = tuple(providers)
        self._logger = logger or logging.getLogger(__name__)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Return de-duplicated results, isolating individual provider failures."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be positive")

        merged: list[SearchResult] = []
        seen: set[str] = set()
        for provider in self._providers:
            if len(merged) == limit:
                break
            try:
                # Request up to the global limit because duplicates or invalid URLs
                # may consume the provider's leading results.
                results = provider.search(query, limit)
            except SearchProviderError as exc:
                self._logger.warning("search provider %s failed: %s", provider.name, exc)
                continue
            for result in results:
                normalized = _normalize_url(result.url)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    merged.append(result)
                    if len(merged) == limit:
                        break
        return merged


def _normalize_url(url: str) -> str:
    """Normalize safe HTTP(S) URLs for result de-duplication."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    hostname = parts.hostname.lower()
    default_port = (parts.scheme.lower() == "http" and port == 80) or (
        parts.scheme.lower() == "https" and port == 443
    )
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    normalized = SplitResult(
        parts.scheme.lower(), netloc, parts.path.rstrip("/") or "/", parts.query, ""
    )
    return urlunsplit(normalized)
