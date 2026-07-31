"""Live search limit tests through a fake SearchManager boundary."""

from live.search import BoundedSearchManager


class FakeManager:
    """Record the requested provider-independent result limit."""

    def __init__(self) -> None:
        self.limit = 0

    def search(self, query: str, limit: int):
        self.limit = limit
        return []


def test_live_search_manager_clamps_results() -> None:
    fake = FakeManager()
    assert BoundedSearchManager(fake, 10).search("query", 20) == []
    assert fake.limit == 10
