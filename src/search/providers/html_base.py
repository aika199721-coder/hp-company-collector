"""Shared injectable transport and parsing helpers for free HTML search providers."""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol

import requests

from search.providers.base import (
    ProviderResponseMetadata,
    SearchProvider,
    SearchProviderError,
    SearchResult,
)

SEARCH_USER_AGENT = "hp-company-collector/0.10"


class HtmlResponse(Protocol):
    content: bytes
    status_code: int
    url: str

    def raise_for_status(self) -> None:
        """Raise for an unsuccessful response."""


class HtmlClient(Protocol):
    def get(
        self,
        url: str,
        *,
        params: dict[str, str],
        timeout: float,
        headers: dict[str, str],
        allow_redirects: bool,
    ) -> HtmlResponse:
        """Perform one HTML search request."""


class HtmlSearchProvider(SearchProvider):
    """Fetch and normalize one free HTML search result page."""

    endpoint: str

    def __init__(self, client: HtmlClient | None = None, timeout_seconds: float = 20.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._client = client or requests.Session()
        self._timeout = timeout_seconds
        self._metadata = ProviderResponseMetadata()

    @property
    def response_metadata(self) -> ProviderResponseMetadata:
        """Return the status and final URL of the last HTML request."""
        return self._metadata

    def search(self, query: str, limit: int) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be positive")
        try:
            response = self._client.get(
                self.endpoint,
                params=self._params(query),
                timeout=self._timeout,
                headers={"User-Agent": SEARCH_USER_AGENT},
                allow_redirects=True,
            )
            status = getattr(response, "status_code", 200)
            final_url = str(getattr(response, "url", self.endpoint))
            self._metadata = ProviderResponseMetadata(status, final_url)
            response.raise_for_status()
            signal = _block_signal(response.content)
            if signal:
                raise SearchProviderError(
                    f"{self.name} returned {signal}",
                    failure_type=signal,
                    http_status=status,
                    final_url=final_url,
                )
            results = self.parse(response.content, limit)
            if not results and not _is_explicit_no_results(response.content):
                raise SearchProviderError(
                    f"{self.name} result selector did not match",
                    failure_type="parser_mismatch",
                    http_status=status,
                    final_url=final_url,
                )
            return results
        except SearchProviderError:
            raise
        except requests.TooManyRedirects as exc:
            raise SearchProviderError(
                f"{self.name} redirect loop", failure_type="redirect"
            ) from exc
        except requests.Timeout as exc:
            raise SearchProviderError(
                f"{self.name} request timed out", failure_type="timeout"
            ) from exc
        except requests.ConnectionError as exc:
            raise SearchProviderError(
                f"{self.name} connection failed", failure_type="connection_error"
            ) from exc
        except requests.HTTPError as exc:
            response = exc.response
            status = response.status_code if response is not None else None
            failure = f"http_{status}" if status in {403, 429} else "http_error"
            final_url = str(response.url) if response is not None else None
            raise SearchProviderError(
                f"{self.name} returned HTTP {status}",
                failure_type=failure,
                http_status=status,
                final_url=final_url,
            ) from exc
        except requests.RequestException as exc:
            raise SearchProviderError(
                f"{self.name} request failed", failure_type="connection_error"
            ) from exc

    def _params(self, query: str) -> dict[str, str]:
        return {"q": query}

    @abstractmethod
    def parse(self, content: bytes, limit: int) -> list[SearchResult]:
        """Parse provider-specific result markup."""


def _block_signal(content: bytes) -> str | None:
    text = content.decode("utf-8", errors="ignore").lower()
    captcha = ("verify you are human", "captchaを入力", "私はロボットではありません")
    blocked = ("access denied", "request blocked", "cloudflare challenge")
    if any(signal in text for signal in captcha):
        return "captcha"
    return "block" if any(signal in text for signal in blocked) else None


def _is_explicit_no_results(content: bytes) -> bool:
    text = content.decode("utf-8", errors="ignore").lower()
    return any(
        marker in text
        for marker in ("no results found", "did not match any documents", "結果がありません")
    )
