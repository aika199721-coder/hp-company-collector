"""Streaming requests client with a hard response-byte ceiling."""

from __future__ import annotations

from typing import Any

import requests


class BoundedHttpClient:
    """Wrap requests.Session and stop reading once the configured ceiling is crossed."""

    def __init__(self, max_response_bytes: int, session: requests.Session | None = None) -> None:
        if max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self._maximum = max_response_bytes
        self._session = session or requests.Session()

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        """Perform a streamed GET compatible with search and crawler clients."""
        kwargs["stream"] = True
        response = self._session.get(url, **kwargs)
        content_length = response.headers.get("content-length", "")
        if content_length.isdigit() and int(content_length) > self._maximum:
            response.headers["x-live-size-exceeded"] = "1"
            response._content = b""
            response.close()
            return response
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=65_536):
            size += len(chunk)
            if size > self._maximum:
                response.headers["x-live-size-exceeded"] = "1"
                chunks = []
                break
            chunks.append(chunk)
        response._content = b"".join(chunks)
        response.close()
        return response
