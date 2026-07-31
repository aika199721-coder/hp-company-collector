"""QueryBuilder unit tests."""

import pytest

from search.query_builder import QueryBuilder, SearchCriteria


def test_builds_deterministic_phrase_query() -> None:
    criteria = SearchCriteria(" 東京都 ", "千代田区", " 飲食店 ")

    assert QueryBuilder().build(criteria) == '"東京都" "千代田区" "飲食店" 公式サイト'


def test_criteria_rejects_each_empty_required_value() -> None:
    with pytest.raises(ValueError, match="prefecture"):
        SearchCriteria(" ", "千代田区", "飲食店")
    with pytest.raises(ValueError, match="municipality"):
        SearchCriteria("東京都", "", "飲食店")
    with pytest.raises(ValueError, match="industry"):
        SearchCriteria("東京都", "千代田区", "\t")


def test_embedded_quotes_cannot_add_query_operators() -> None:
    criteria = SearchCriteria("東京都", '千代田区" OR "大阪市', "飲食店")

    assert QueryBuilder().build(criteria) == '"東京都" "千代田区  OR  大阪市" "飲食店" 公式サイト'
