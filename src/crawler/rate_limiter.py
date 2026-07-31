"""Thread-safe per-origin request rate limiting."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from urllib.parse import urlsplit


class RateLimiter:
    """Enforce a minimum delay independently for each URL origin."""

    def __init__(
        self,
        delay_seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if delay_seconds < 0:
            raise ValueError("delay_seconds must not be negative")
        self.delay_seconds = float(delay_seconds)
        self._clock = clock
        self._sleeper = sleeper
        self._next_allowed: dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str, delay_seconds: float | None = None) -> None:
        """Wait until the origin is eligible and reserve its next request slot."""
        origin = _origin(url)
        delay = self.delay_seconds if delay_seconds is None else float(delay_seconds)
        if delay < 0:
            raise ValueError("delay_seconds must not be negative")
        with self._lock:
            now = self._clock()
            eligible_at = max(now, self._next_allowed.get(origin, now))
            self._next_allowed[origin] = eligible_at + delay
        wait_seconds = eligible_at - now
        if wait_seconds:
            # Sleeping outside the lock keeps unrelated origins independent.
            self._sleeper(wait_seconds)


def _origin(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("url must be an absolute HTTP(S) URL")
    port = parts.port
    default_port = (parts.scheme.lower() == "http" and port == 80) or (
        parts.scheme.lower() == "https" and port == 443
    )
    authority = (
        parts.hostname.lower()
        if port is None or default_port
        else f"{parts.hostname.lower()}:{port}"
    )
    return f"{parts.scheme.lower()}://{authority}"
