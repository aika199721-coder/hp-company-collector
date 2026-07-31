"""Search orchestration boundary hiding the ordered ProviderChain."""

from __future__ import annotations

import logging

from search.provider_chain import ProviderAuditor, ProviderChain
from search.providers.base import SearchProvider, SearchResult


class SearchManager:
    """Expose one provider-independent search API to coordinators."""

    def __init__(
        self,
        providers: list[SearchProvider],
        logger: logging.Logger | None = None,
        priorities: dict[str, int] | None = None,
        auditor: ProviderAuditor | None = None,
        configured: dict[str, bool] | None = None,
    ) -> None:
        self._chain = ProviderChain(providers, priorities, logger, auditor, configured)

    def set_run_id(self, run_id: str) -> None:
        """Associate subsequent provider audits with an application run."""
        self._chain.set_run_id(run_id)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Return scored, normalized, cross-provider de-duplicated results."""
        return self._chain.search(query, limit)
