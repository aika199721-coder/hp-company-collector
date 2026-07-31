"""Bounded fetch decorator that stops rather than bypassing access controls."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

from crawler.result import FetchResult
from live.audit import HttpAuditEntry, HttpAuditRepository
from live.config import LiveValidationConfig

_CAPTCHA_SIGNALS = ("captcha", "reCAPTCHA", "私はロボットではありません")
_BLOCK_SIGNALS = ("access denied", "アクセスが拒否", "forbidden", "temporarily blocked")


class LiveSafetyFetcher:
    """Enforce live-run request, domain, time, content, and block ceilings."""

    def __init__(
        self,
        delegate: object,
        config: LiveValidationConfig,
        audit: HttpAuditRepository,
        run_id: str,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._delegate = delegate
        self._config = config
        self._audit = audit
        self._run_id = run_id
        self._monotonic = monotonic
        self._now = now
        self._started = monotonic()
        self._total = 0
        self._domains: Counter[str] = Counter()
        self._forbidden: Counter[str] = Counter()
        self._stopped: set[str] = set()

    def fetch(self, url: str) -> FetchResult:
        """Fetch once or return a safe failure without attempting a request."""
        domain = (urlsplit(url).hostname or "").lower()
        blocked = self._preflight_error(domain)
        if blocked:
            return FetchResult(url, url, None, error=blocked)
        requested_at = self._now()
        started = self._monotonic()
        self._total += 1
        self._domains[domain] += 1
        result = self._delegate.fetch(url)
        safe_result, category = self._inspect(result, domain)
        finished_at = self._now()
        self._audit.save(
            HttpAuditEntry(
                self._run_id,
                url,
                safe_result.final_url,
                domain,
                requested_at.isoformat(),
                finished_at.isoformat(),
                max(0, int((self._monotonic() - started) * 1000)),
                safe_result.status_code,
                safe_result.headers.get("content-type", ""),
                len(result.content),
                safe_result.encoding,
                len(safe_result.redirect_chain),
                safe_result.error != "robots_denied",
                self._config.delay_seconds,
                safe_result.from_playwright,
                category,
                safe_result.error,
            )
        )
        return safe_result

    def _preflight_error(self, domain: str) -> str | None:
        if domain in self._stopped:
            return "domain_stopped"
        if self._total >= self._config.max_http_requests:
            return "run_http_limit"
        if self._domains[domain] >= self._config.max_requests_per_domain:
            self._stopped.add(domain)
            return "domain_http_limit"
        if self._monotonic() - self._started >= self._config.max_runtime_seconds:
            return "run_time_limit"
        return None

    def _inspect(self, result: FetchResult, domain: str) -> tuple[FetchResult, str]:
        error = result.error
        content_type = result.headers.get("content-type", "").lower()
        if error == "robots_denied" and self._config.stop_on_robots_error:
            self._stopped.add(domain)
        if result.status_code == 429 and self._config.stop_on_rate_limit:
            self._stopped.add(domain)
            error = "rate_limited_domain"
        if result.status_code == 403:
            self._forbidden[domain] += 1
            if self._forbidden[domain] >= self._config.consecutive_403_limit:
                self._stopped.add(domain)
                error = "repeated_403"
        if len(set(result.redirect_chain)) != len(result.redirect_chain):
            self._stopped.add(domain)
            error = "redirect_loop"
        size_exceeded = (
            result.headers.get("x-live-size-exceeded") == "1"
            or len(result.content) > self._config.max_response_bytes
        )
        if size_exceeded:
            error = "response_too_large"
        elif result.content and not _is_html(content_type):
            error = "non_html_content"
        text = result.text[:200_000].lower()
        if self._config.stop_on_captcha_signal and _contains(text, _CAPTCHA_SIGNALS):
            self._stopped.add(domain)
            error = "captcha_signal"
        if self._config.stop_on_block_page_signal and _contains(text, _BLOCK_SIGNALS):
            self._stopped.add(domain)
            error = "block_page_signal"
        if not error:
            return result, "html"
        return _without_body(result, error), error


def _is_html(content_type: str) -> bool:
    return content_type.split(";", 1)[0].strip() in {"text/html", "application/xhtml+xml"}


def _contains(text: str, signals: tuple[str, ...]) -> bool:
    return any(signal.lower() in text for signal in signals)


def _without_body(result: FetchResult, error: str) -> FetchResult:
    return FetchResult(
        result.requested_url,
        result.final_url,
        result.status_code,
        result.headers,
        b"",
        result.encoding,
        result.redirect_chain,
        result.from_playwright,
        error,
    )
