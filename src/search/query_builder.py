"""Validated search query construction for Japanese business searches."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchCriteria:
    """Required geographic and industry inputs for one search."""

    prefecture: str
    municipality: str
    industry: str

    def __post_init__(self) -> None:
        """Normalize surrounding whitespace and reject incomplete criteria."""
        for field_name in ("prefecture", "municipality", "industry"):
            value = getattr(self, field_name).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, value)


class QueryBuilder:
    """Build conservative provider-independent official-site queries."""

    def build(self, criteria: SearchCriteria) -> str:
        """Return a deterministic query with each user term phrase-quoted."""
        terms = (
            self._quote(criteria.prefecture),
            self._quote(criteria.municipality),
            self._quote(criteria.industry),
            "公式サイト",
        )
        return " ".join(terms)

    @staticmethod
    def _quote(value: str) -> str:
        # Avoid allowing embedded quotes to alter provider query structure.
        return f'"{value.replace(chr(34), " ").strip()}"'
