"""Search provider implementations and contracts."""

from search.providers.base import SearchProvider, SearchProviderError, SearchResult
from search.providers.bing_rss import BingRSSProvider

__all__ = ["BingRSSProvider", "SearchProvider", "SearchProviderError", "SearchResult"]
