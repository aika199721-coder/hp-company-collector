"""Graceful shutdown state tests."""

from application.shutdown import ShutdownController


def test_shutdown_request_is_idempotent() -> None:
    controller = ShutdownController()

    assert controller.request("first", "SIGTERM") is True
    assert controller.request("second", "SIGINT") is False
    assert controller.reason == "first"
    assert controller.signal_name == "SIGTERM"
