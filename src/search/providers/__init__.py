"""Search provider implementations and contracts."""

from search.providers.base import SearchProvider, SearchProviderError, SearchResult
from search.providers.bing_rss import BingRSSProvider
from search.providers.brave import BraveSearchProvider
from search.providers.duckduckgo import DuckDuckGoHtmlProvider
from search.providers.mojeek import MojeekProvider
from search.providers.searxng import SearXNGProvider

__all__ = [
    "BingRSSProvider",
    "BraveSearchProvider",
    "DuckDuckGoHtmlProvider",
    "MojeekProvider",
    "SearXNGProvider",
    "SearchProvider",
    "SearchProviderError",
    "SearchResult",
]
