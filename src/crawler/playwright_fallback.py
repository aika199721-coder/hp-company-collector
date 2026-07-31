"""Injectable Playwright page fallback with no HTML analysis."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import Protocol

from crawler.result import FetchResult


class PlaywrightResponse(Protocol):
    """Subset of a Playwright response used by the fallback."""

    @property
    def status(self) -> int:
        """Return HTTP status."""

    @property
    def headers(self) -> Mapping[str, str]:
        """Return response headers."""


class PlaywrightPage(Protocol):
    """Subset of a synchronous Playwright page used by the fallback."""

    @property
    def url(self) -> str:
        """Return the final page URL."""

    def goto(self, url: str, *, wait_until: str, timeout: float) -> PlaywrightResponse | None:
        """Navigate to a URL."""

    def content(self) -> str:
        """Return unparsed page source."""


class PlaywrightFallback:
    """Fetch page source using an injected, managed Playwright page."""

    def __init__(
        self, page_factory: Callable[[], AbstractContextManager[PlaywrightPage]]
    ) -> None:
        self._page_factory = page_factory

    def fetch(self, url: str, timeout_seconds: float) -> FetchResult:
        """Navigate once and return transport metadata and unparsed source."""
        with self._page_factory() as page:
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
            if response is None:
                return FetchResult(
                    url,
                    page.url or url,
                    None,
                    error="playwright_no_response",
                    from_playwright=True,
                )
            headers = dict(response.headers)
            encoding = _header_encoding(headers.get("content-type", ""))
            return FetchResult(
                requested_url=url,
                final_url=page.url,
                status_code=response.status,
                headers=headers,
                content=page.content().encode(encoding, errors="replace"),
                encoding=encoding,
                from_playwright=True,
            )


def _header_encoding(content_type: str) -> str:
    for parameter in content_type.split(";")[1:]:
        name, separator, value = parameter.strip().partition("=")
        if separator and name.lower() == "charset":
            return value.strip(' "\'') or "utf-8"
    return "utf-8"
