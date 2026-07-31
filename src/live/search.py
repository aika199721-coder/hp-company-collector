"""Search ceiling decorator for live validation."""

from __future__ import annotations

from search.providers.base import SearchResult


class BoundedSearchManager:
    """Clamp provider result counts without calling providers directly."""

    def __init__(self, delegate: object, max_results_per_query: int) -> None:
        self._delegate = delegate
        self._maximum = max_results_per_query

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Delegate only through SearchManager using the smaller live ceiling."""
        return self._delegate.search(query, min(limit, self._maximum))

    def set_run_id(self, run_id: str) -> None:
        """Forward the audit run identifier to the shared SearchManager."""
        setter = getattr(self._delegate, "set_run_id", None)
        if setter is not None:
            setter(run_id)
