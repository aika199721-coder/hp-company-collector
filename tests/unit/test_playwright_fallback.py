"""Playwright fallback tests using injected page mocks only."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import ClassVar

from crawler.playwright_fallback import PlaywrightFallback


class FakeResponse:
    status = 200
    headers: ClassVar = {"content-type": "text/html; charset=shift_jis"}


class FakePage:
    """Minimal synchronous Playwright page mock."""

    url = "https://company.example.jp/final"

    def __init__(self) -> None:
        self.goto_args: tuple[str, str, float] | None = None

    def goto(self, url: str, *, wait_until: str, timeout: float) -> FakeResponse:
        """Record navigation and return a response mock."""
        self.goto_args = (url, wait_until, timeout)
        return FakeResponse()

    def content(self) -> str:
        """Return source without parsing it."""
        return "会社ページ"


def test_fetches_unparsed_source_through_injected_page() -> None:
    page = FakePage()

    @contextmanager
    def factory() -> Iterator[FakePage]:
        yield page

    result = PlaywrightFallback(factory).fetch("https://company.example.jp", 2.5)

    assert result.status_code == 200
    assert result.final_url.endswith("/final")
    assert result.from_playwright is True
    assert result.encoding == "shift_jis"
    assert result.text == "会社ページ"
    assert page.goto_args == ("https://company.example.jp", "domcontentloaded", 2500.0)
