"""SearchProvider contract tests."""

import pytest

from search.providers.base import SearchProvider, SearchResult


def test_abstract_provider_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        SearchProvider()  # type: ignore[abstract]


def test_search_result_is_immutable() -> None:
    result = SearchResult("title", "https://example.jp/", "snippet", "test", 1)

    with pytest.raises(AttributeError):
        result.rank = 2  # type: ignore[misc]
