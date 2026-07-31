"""FetchResult transport model tests."""

import pytest

from crawler.result import FetchResult


def test_decodes_content_and_defensively_freezes_headers() -> None:
    headers = {"content-type": "text/plain"}
    result = FetchResult("https://example.jp", "https://example.jp", 200, headers, "会社".encode())
    headers["changed"] = "yes"

    assert result.text == "会社"
    assert "changed" not in result.headers
    with pytest.raises(TypeError):
        result.headers["x"] = "y"  # type: ignore[index]


def test_unknown_encoding_falls_back_to_utf8() -> None:
    result = FetchResult(
        "https://example.jp",
        "https://example.jp",
        200,
        content=b"text",
        encoding="unknown-x",
    )

    assert result.text == "text"
