"""Provider contract and normalized search result types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class SearchProviderError(RuntimeError):
    """Raised when a provider cannot return valid search results."""


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


class SearchProvider(ABC):
    """Interface implemented by all free search providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the stable provider identifier used in configuration and storage."""

    @abstractmethod
    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Search for a query and return at most ``limit`` normalized results."""
