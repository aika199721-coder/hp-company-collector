"""Idempotent graceful-shutdown state shared by the application layer."""

from __future__ import annotations

import signal
from threading import Event, Lock
from types import FrameType


class ShutdownController:
    """Record the first shutdown request without running cleanup in a signal handler."""

    def __init__(self) -> None:
        self._event = Event()
        self._lock = Lock()
        self.reason: str | None = None
        self.signal_name: str | None = None

    def request(self, reason: str, signal_name: str | None = None) -> bool:
        """Record the first request and report whether it was newly accepted."""
        with self._lock:
            if self._event.is_set():
                return False
            self.reason = reason
            self.signal_name = signal_name
            self._event.set()
            return True

    def is_requested(self) -> bool:
        """Return whether collection should stop claiming new candidates."""
        return self._event.is_set()

    def install(self) -> None:
        """Install lightweight SIGINT and SIGTERM handlers."""
        signal.signal(signal.SIGINT, self._handle)
        signal.signal(signal.SIGTERM, self._handle)

    def _handle(self, number: int, _frame: FrameType | None) -> None:
        name = signal.Signals(number).name
        self.request(f"signal:{name}", name)
