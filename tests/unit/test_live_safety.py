"""Fake-HTTP-only live fetch safety and audit tests."""

from dataclasses import replace
from pathlib import Path

from crawler.result import FetchResult
from live.audit import HttpAuditRepository
from live.config import LiveValidationConfig
from live.safety import LiveSafetyFetcher
from storage.sqlite import Database

ROOT = Path(__file__).resolve().parents[2]


class FakeFetcher:
    """Return configured responses without external access."""

    def __init__(self, results: list[FetchResult]) -> None:
        self.results = results
        self.calls = 0

    def fetch(self, url: str) -> FetchResult:
        result = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return result


def _result(status: int = 200, content: bytes = b"<html>ok</html>", **kwargs) -> FetchResult:
    return FetchResult(
        "https://example.test/",
        "https://example.test/",
        status,
        {"content-type": "text/html; charset=utf-8"},
        content,
        **kwargs,
    )


def _safety(tmp_path: Path, results: list[FetchResult], **changes):
    database = Database(tmp_path / "live.sqlite3")
    database.initialize()
    config = replace(LiveValidationConfig.load(ROOT / "config/live_validation.yaml"), **changes)
    fake = FakeFetcher(results)
    return LiveSafetyFetcher(fake, config, HttpAuditRepository(database), "run-1"), fake, database


def test_size_non_html_redirect_and_signals_are_stopped_and_audited(tmp_path: Path) -> None:
    results = [
        _result(content=b"x" * 11),
        FetchResult(
            "https://example.test/",
            "https://example.test/",
            200,
            {"content-type": "application/pdf"},
            b"pdf",
        ),
        _result(
            content=b"ok",
            redirect_chain=("https://example.test/a", "https://example.test/a"),
        ),
    ]
    safety, _, database = _safety(tmp_path, results, max_response_bytes=10)

    assert safety.fetch("https://a.test/").error == "response_too_large"
    assert safety.fetch("https://b.test/").error == "non_html_content"
    assert safety.fetch("https://c.test/").error == "redirect_loop"
    with database.connect() as connection:
        row = connection.execute("SELECT * FROM http_audit_logs LIMIT 1").fetchone()
        columns = {item[1] for item in connection.execute("PRAGMA table_info(http_audit_logs)")}
    assert row["content_length"] == 11
    assert "content" not in columns and "cookie" not in columns


def test_request_domain_time_rate_limit_forbidden_and_captcha_stops(tmp_path: Path) -> None:
    results = [
        _result(429),
        _result(403),
        _result(403),
        _result(content=b"<title>Verify you are human</title>"),
    ]
    safety, fake, _ = _safety(tmp_path, results, max_http_requests=4, max_requests_per_domain=3)

    assert safety.fetch("https://rate.test/").error == "rate_limited_domain"
    assert safety.fetch("https://rate.test/next").error == "domain_stopped"
    assert safety.fetch("https://deny.test/1").status_code == 403
    assert safety.fetch("https://deny.test/2").error == "repeated_403"
    assert safety.fetch("https://captcha.test/").error == "captcha_signal"
    assert fake.calls == 4


def test_total_domain_and_runtime_preflight_limits_do_not_fetch(tmp_path: Path) -> None:
    safety, fake, _ = _safety(tmp_path, [_result()], max_http_requests=1)
    assert safety.fetch("https://one.test/").error is None
    assert safety.fetch("https://two.test/").error == "run_http_limit"
    assert fake.calls == 1


def test_domain_runtime_robots_and_block_controls(tmp_path: Path) -> None:
    safety, fake, database = _safety(
        tmp_path,
        [_result(), _result(error="robots_denied"), _result(content=b"access denied")],
        max_requests_per_domain=1,
    )
    assert safety.fetch("https://domain.test/one").error is None
    assert safety.fetch("https://domain.test/two").error == "domain_http_limit"
    assert safety.fetch("https://robots.test/").error == "robots_denied"
    assert safety.fetch("https://blocked.test/").error == "block_page_signal"
    assert fake.calls == 3

    config = replace(
        LiveValidationConfig.load(ROOT / "config/live_validation.yaml"),
        max_runtime_seconds=1,
    )
    clock_value = [0.0]
    timed = LiveSafetyFetcher(
        FakeFetcher([_result()]),
        config,
        HttpAuditRepository(database),
        "run-time",
        monotonic=lambda: clock_value[0],
    )
    clock_value[0] = 2.0
    assert timed.fetch("https://time.test/").error == "run_time_limit"
