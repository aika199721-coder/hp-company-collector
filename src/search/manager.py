"""Search orchestration boundary hiding the ordered ProviderChain."""

from __future__ import annotations

import logging

from search.provider_chain import ProviderChain
from search.providers.base import SearchProvider, SearchResult


class SearchManager:
    """Expose one provider-independent search API to coordinators."""

    def __init__(
        self,
        providers: list[SearchProvider],
        logger: logging.Logger | None = None,
        priorities: dict[str, int] | None = None,
    ) -> None:
        self._chain = ProviderChain(providers, priorities, logger)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Return scored, normalized, cross-provider de-duplicated results."""
        return self._chain.search(query, limit)
