"""Optional operator-supplied SearXNG JSON provider."""

from __future__ import annotations

from typing import Any

import requests

from search.providers.base import SearchProvider, SearchProviderError, SearchResult


class SearXNGProvider(SearchProvider):
    """Use only an explicitly configured SearXNG instance."""

    def __init__(self, base_url: str, client: Any = None, timeout_seconds: float = 20.0) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("SearXNG base_url must be absolute HTTP(S)")
        self._endpoint = base_url.rstrip("/") + "/search"
        self._client = client or requests.Session()
        self._timeout = timeout_seconds

    @property
    def name(self) -> str:
        return "searxng"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        try:
            response = self._client.get(
                self._endpoint,
                params={"q": query, "format": "json", "language": "ja"},
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise SearchProviderError("SearXNG request failed") from exc
        results: list[SearchResult] = []
        for item in payload.get("results", []):
            url = str(item.get("url", ""))
            title = str(item.get("title", ""))
            if not url or not title:
                continue
            results.append(
                SearchResult(title, url, str(item.get("content", "")), self.name, len(results) + 1)
            )
            if len(results) >= limit:
                break
        return results
