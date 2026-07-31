"""Shared injectable transport and parsing helpers for free HTML search providers."""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol

import requests

from search.providers.base import SearchProvider, SearchProviderError, SearchResult


class HtmlResponse(Protocol):
    content: bytes

    def raise_for_status(self) -> None:
        """Raise for an unsuccessful response."""


class HtmlClient(Protocol):
    def get(self, url: str, *, params: dict[str, str], timeout: float) -> HtmlResponse:
        """Perform one HTML search request."""


class HtmlSearchProvider(SearchProvider):
    """Fetch and normalize one free HTML search result page."""

    endpoint: str

    def __init__(self, client: HtmlClient | None = None, timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._client = client or requests.Session()
        self._timeout = timeout_seconds

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be positive")
        try:
            response = self._client.get(
                self.endpoint, params=self._params(query), timeout=self._timeout
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SearchProviderError(f"{self.name} request failed") from exc
        return self.parse(response.content, limit)

    def _params(self, query: str) -> dict[str, str]:
        return {"q": query}

    @abstractmethod
    def parse(self, content: bytes, limit: int) -> list[SearchResult]:
        """Parse provider-specific result markup."""
