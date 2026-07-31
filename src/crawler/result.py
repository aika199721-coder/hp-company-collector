"""Transport-only result returned by crawler fetchers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class FetchResult:
    """Raw response metadata and bytes; no company information is extracted."""

    requested_url: str
    final_url: str
    status_code: int | None
    headers: Mapping[str, str] = field(default_factory=dict)
    content: bytes = b""
    encoding: str = "utf-8"
    redirect_chain: tuple[str, ...] = ()
    from_playwright: bool = False
    error: str | None = None

    def __post_init__(self) -> None:
        """Freeze a defensive copy of response headers."""
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))

    @property
    def text(self) -> str:
        """Decode raw content without performing HTML parsing."""
        try:
            return self.content.decode(self.encoding, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")
