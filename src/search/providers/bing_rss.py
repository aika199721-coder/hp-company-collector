"""Bing RSS search provider."""

from __future__ import annotations

from typing import Protocol

import requests

from search.providers.base import SearchProvider, SearchProviderError, SearchResult
from search.result_parser import parse_bing_rss


class HttpResponse(Protocol):
    """Minimal response interface required from an HTTP client."""

    content: bytes

    def raise_for_status(self) -> None:
        """Raise when the response status is unsuccessful."""


class HttpClient(Protocol):
    """Injectable HTTP interface that keeps provider tests offline."""

    def get(
        self, url: str, *, params: dict[str, str | int], timeout: float
    ) -> HttpResponse:
        """Perform an HTTP GET request."""


class BingRSSProvider(SearchProvider):
    """Retrieve and parse the free RSS representation of Bing results."""

    endpoint = "https://www.bing.com/search"

    def __init__(self, client: HttpClient | None = None, timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._client = client or requests.Session()
        self._timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        """Return the provider configuration identifier."""
        return "bing_rss"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Fetch one RSS response and return normalized results."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be positive")
        try:
            response = self._client.get(
                self.endpoint,
                params={"q": query, "format": "rss", "count": limit},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SearchProviderError("Bing RSS request failed") from exc
        return parse_bing_rss(response.content, limit)
