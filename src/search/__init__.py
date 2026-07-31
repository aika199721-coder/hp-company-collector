"""Public search foundation API."""

from search.manager import SearchManager
from search.query_builder import QueryBuilder, SearchCriteria

__all__ = ["QueryBuilder", "SearchCriteria", "SearchManager"]
