"""Provider contract and normalized search result types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class SearchProviderError(RuntimeError):
    """Raised with audit-safe metadata when a provider cannot return results."""

    def __init__(
        self,
        message: str,
        *,
        failure_type: str = "provider_error",
        http_status: int | None = None,
        final_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_type = failure_type
        self.http_status = http_status
        self.final_url = final_url


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Provider-independent representation of one search result."""

    title: str
    url: str
    snippet: str
    provider: str
    rank: int
    match_score: float = 0.0
    chain_score: float = 0.0


@dataclass(frozen=True, slots=True)
class ProviderResponseMetadata:
    """Audit-safe metadata from the most recent provider HTTP response."""

    http_status: int | None = None
    final_url: str | None = None


class SearchProvider(ABC):
    """Interface implemented by all free search providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable provider identifier used in configuration and storage."""

    @abstractmethod
    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Search for a query and return at most ``limit`` normalized results."""

    @property
    def response_metadata(self) -> ProviderResponseMetadata:
        """Return HTTP metadata without exposing bodies, cookies, or credentials."""
        return ProviderResponseMetadata()
