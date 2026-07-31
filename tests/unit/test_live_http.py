"""Streaming byte ceiling tests with a fake requests session."""

from live.http import BoundedHttpClient


class FakeResponse:
    """Minimal streamed response."""

    def __init__(self, chunks: list[bytes], length: str = "") -> None:
        self.headers = {"content-length": length} if length else {}
        self._chunks = chunks
        self._content = b""
        self.closed = False

    def iter_content(self, chunk_size: int):
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


class FakeSession:
    """Capture stream mode without networking."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.kwargs = {}

    def get(self, url: str, **kwargs):
        self.kwargs = kwargs
        return self.response


def test_streaming_client_stops_oversized_body() -> None:
    response = FakeResponse([b"1234", b"5678"])
    session = FakeSession(response)

    result = BoundedHttpClient(5, session).get("https://example.test/")

    assert session.kwargs["stream"] is True
    assert result.headers["x-live-size-exceeded"] == "1"
    assert result._content == b""
    assert result.closed is True
