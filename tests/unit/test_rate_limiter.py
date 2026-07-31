"""Deterministic RateLimiter tests without real sleeping."""

import pytest

from crawler.rate_limiter import RateLimiter


class FakeTime:
    """Controllable monotonic clock and sleeper."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        """Return current fake monotonic time."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Record and advance fake time."""
        self.sleeps.append(seconds)
        self.now += seconds


def test_waits_per_origin_and_keeps_origins_independent() -> None:
    fake = FakeTime()
    limiter = RateLimiter(2, clock=fake.clock, sleeper=fake.sleep)

    limiter.wait("https://example.jp/one")
    limiter.wait("https://other.example.jp/one")
    limiter.wait("https://example.jp/two")

    assert fake.sleeps == [2.0]


def test_supports_larger_per_call_robots_delay() -> None:
    fake = FakeTime()
    limiter = RateLimiter(1, clock=fake.clock, sleeper=fake.sleep)

    limiter.wait("https://example.jp/one", delay_seconds=3)
    limiter.wait("https://example.jp/two")

    assert fake.sleeps == [3.0]


def test_rejects_invalid_delay_and_url() -> None:
    with pytest.raises(ValueError, match="negative"):
        RateLimiter(-1)
    with pytest.raises(ValueError, match="absolute"):
        RateLimiter(0).wait("/relative")
