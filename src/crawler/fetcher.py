"""robots-aware requests fetcher with injectable transport and browser fallback."""

from __future__ import annotations

import gzip
from collections.abc import Mapping
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import requests

from crawler.encoding import detect_html_encoding
from crawler.result import FetchResult

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class HttpResponse(Protocol):
    """Minimal requests response contract."""

    status_code: int
    content: bytes
    headers: Mapping[str, str]
    url: str
    encoding: str | None
    apparent_encoding: str | None


class HttpClient(Protocol):
    """Injectable requests-compatible HTTP client."""

    def get(
        self,
        url: str,
        *,
        timeout: float,
        allow_redirects: bool,
        headers: Mapping[str, str],
    ) -> HttpResponse:
        """Perform one HTTP GET without automatic redirects."""


class RobotsChecker(Protocol):
    """Access-policy interface used before every request and redirect."""

    def can_fetch(self, url: str) -> bool:
        """Return whether a URL may be requested."""


class RequestRateLimiter(Protocol):
    """Injectable per-origin pacing interface."""

    def wait(self, url: str, delay_seconds: float | None = None) -> None:
        """Wait until a URL origin is eligible."""


class BrowserFallback(Protocol):
    """Injectable browser fallback interface."""

    def fetch(self, url: str, timeout_seconds: float) -> FetchResult:
        """Fetch a URL with a browser and return raw page source."""


class Fetcher:
    """Fetch raw documents while enforcing robots and per-origin pacing."""

    def __init__(
        self,
        robots: RobotsChecker,
        rate_limiter: RequestRateLimiter,
        *,
        client: HttpClient | None = None,
        playwright: BrowserFallback | None = None,
        user_agent: str = "hp-company-collector/4.0",
        timeout_seconds: float = 20.0,
        max_redirects: int = 5,
    ) -> None:
        if not user_agent.strip():
            raise ValueError("user_agent must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_redirects < 0:
            raise ValueError("max_redirects must not be negative")
        self._robots = robots
        self._rate_limiter = rate_limiter
        self._client = client or requests.Session()
        self._playwright = playwright
        self._user_agent = user_agent
        self._timeout_seconds = timeout_seconds
        self._max_redirects = max_redirects

    def fetch(self, url: str) -> FetchResult:
        """Fetch a raw URL, manually validating every redirect target."""
        _validate_url(url)
        requested_url = url
        current_url = url
        redirects: list[str] = []

        while True:
            if not self._robots.can_fetch(current_url):
                return FetchResult(
                    requested_url,
                    current_url,
                    None,
                    redirect_chain=tuple(redirects),
                    error="robots_denied",
                )
            self._rate_limiter.wait(current_url)
            try:
                response = self._client.get(
                    current_url,
                    timeout=self._timeout_seconds,
                    allow_redirects=False,
                    headers={"User-Agent": self._user_agent, "Accept-Encoding": "gzip, deflate"},
                )
            except requests.Timeout:
                return FetchResult(requested_url, current_url, None, error="timeout")
            except requests.RequestException:
                return FetchResult(requested_url, current_url, None, error="request_error")

            headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
            if response.status_code in _REDIRECT_STATUSES:
                location = headers.get("location")
                if not location:
                    return self._result(
                        requested_url, response, redirects, error="redirect_missing_location"
                    )
                if len(redirects) >= self._max_redirects:
                    return self._result(
                        requested_url, response, redirects, error="too_many_redirects"
                    )
                current_url = urljoin(current_url, location)
                try:
                    _validate_url(current_url)
                except ValueError:
                    return self._result(requested_url, response, redirects, error="unsafe_redirect")
                redirects.append(current_url)
                continue

            result = self._result(requested_url, response, redirects)
            if response.status_code == 403 and self._playwright is not None:
                browser_result = self._playwright.fetch(current_url, self._timeout_seconds)
                return FetchResult(
                    requested_url=requested_url,
                    final_url=browser_result.final_url,
                    status_code=browser_result.status_code,
                    headers=browser_result.headers,
                    content=browser_result.content,
                    encoding=browser_result.encoding,
                    redirect_chain=tuple(redirects),
                    from_playwright=True,
                    error=browser_result.error,
                )
            return result

    @staticmethod
    def _result(
        requested_url: str,
        response: HttpResponse,
        redirects: list[str],
        *,
        error: str | None = None,
    ) -> FetchResult:
        headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
        content = response.content
        if content.startswith(b"\x1f\x8b"):
            try:
                content = gzip.decompress(content)
            except gzip.BadGzipFile:
                error = error or "invalid_gzip"
        encoding = detect_html_encoding(
            content,
            headers,
            getattr(response, "apparent_encoding", None),
        )
        return FetchResult(
            requested_url=requested_url,
            final_url=response.url,
            status_code=response.status_code,
            headers=headers,
            content=content,
            encoding=encoding or "utf-8",
            redirect_chain=tuple(redirects),
            error=error,
        )


def _validate_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        _ = parts.port
    except ValueError as exc:
        raise ValueError("url must be an absolute HTTP(S) URL") from exc
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("url must be an absolute HTTP(S) URL")
