"""Validated search query construction for Japanese business searches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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

    def __init__(self, synonyms: Mapping[str, Sequence[str]] | None = None) -> None:
        self._synonyms = {
            key: tuple(dict.fromkeys(item.strip() for item in values if item.strip()))
            for key, values in (synonyms or {}).items()
        }

    def build(self, criteria: SearchCriteria) -> str:
        """Return a deterministic query with each user term phrase-quoted."""
        terms = (
            self._quote(criteria.prefecture),
            self._quote(criteria.municipality),
            self._quote(criteria.industry),
            "公式サイト",
        )
        return " ".join(terms)

    def build_many(self, criteria: SearchCriteria) -> tuple[str, ...]:
        """Build diverse city/industry queries without over-weighting prefectures."""
        synonyms = self._synonyms.get(criteria.industry, (criteria.industry,))
        alternatives = tuple(item for item in synonyms if item != criteria.industry)
        first = alternatives[0] if alternatives else criteria.industry
        second = alternatives[1] if len(alternatives) > 1 else first
        short_city = criteria.municipality.removesuffix("市").removesuffix("区")
        values = (
            f"{criteria.municipality} {criteria.industry}",
            f"{criteria.municipality} {first}",
            f"{short_city} {second}",
            f"{criteria.municipality} {criteria.industry} 公式",
            f"site:.jp {criteria.municipality} {criteria.industry}",
        )
        return tuple(dict.fromkeys(value.strip() for value in values))

    @staticmethod
    def _quote(value: str) -> str:
        # Avoid allowing embedded quotes to alter provider query structure.
        return f'"{value.replace(chr(34), " ").strip()}"'
