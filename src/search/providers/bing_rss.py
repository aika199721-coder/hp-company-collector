"""Bing RSS search provider."""

from __future__ import annotations

from typing import Protocol

import requests

from search.providers.base import (
    ProviderResponseMetadata,
    SearchProvider,
    SearchProviderError,
    SearchResult,
)
from search.providers.html_base import SEARCH_USER_AGENT
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
        self._metadata = ProviderResponseMetadata()

    @property
    def response_metadata(self) -> ProviderResponseMetadata:
        """Return status and final URL from the most recent RSS request."""
        return self._metadata

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
                headers={"User-Agent": SEARCH_USER_AGENT},
                allow_redirects=True,
            )
            status = getattr(response, "status_code", 200)
            final_url = str(getattr(response, "url", self.endpoint))
            self._metadata = ProviderResponseMetadata(status, final_url)
            response.raise_for_status()
        except requests.TooManyRedirects as exc:
            raise SearchProviderError(
                "Bing RSS redirect loop", failure_type="redirect"
            ) from exc
        except requests.Timeout as exc:
            raise SearchProviderError("Bing RSS timeout", failure_type="timeout") from exc
        except requests.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else None
            raise SearchProviderError(
                f"Bing RSS returned HTTP {status}",
                failure_type=f"http_{status}" if status in {403, 429} else "http_error",
                http_status=status,
                final_url=str(response.url) if response is not None else None,
            ) from exc
        except requests.RequestException as exc:
            raise SearchProviderError(
                "Bing RSS request failed", failure_type="connection_error"
            ) from exc
        try:
            return parse_bing_rss(response.content, limit)
        except SearchProviderError as exc:
            raise SearchProviderError(
                str(exc),
                failure_type="parser_mismatch",
                http_status=self._metadata.http_status,
                final_url=self._metadata.final_url,
            ) from exc
