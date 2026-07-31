"""JSON-LD parsing for supported organization and local-business types."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup

SUPPORTED_TYPES = frozenset(
    {"Organization", "LocalBusiness", "HairSalon", "MedicalBusiness", "Restaurant"}
)


@dataclass(frozen=True, slots=True)
class JsonLdEntity:
    """Supported JSON-LD entity with normalized types and original data."""

    types: tuple[str, ...]
    data: dict[str, Any]

    @property
    def name(self) -> str | None:
        """Return a non-empty entity name when present."""
        value = self.data.get("name")
        return value.strip() if isinstance(value, str) and value.strip() else None


class JsonLdParser:
    """Parse supported JSON-LD entities from an already-fetched document."""

    def parse(self, soup: BeautifulSoup) -> list[JsonLdEntity]:
        """Return supported entities, ignoring malformed or unrelated blocks."""
        entities: list[JsonLdEntity] = []
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text()
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                continue
            for candidate in _objects(value):
                types = _types(candidate.get("@type"))
                if SUPPORTED_TYPES.intersection(types):
                    entities.append(JsonLdEntity(types, candidate))
        return entities


def _objects(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for entry in value for item in _objects(entry)]
    if not isinstance(value, dict):
        return []
    graph = value.get("@graph")
    if isinstance(graph, list):
        return [item for entry in graph for item in _objects(entry)]
    return [value]


def _types(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.rsplit("/", 1)[-1],)
    if isinstance(value, list):
        return tuple(item.rsplit("/", 1)[-1] for item in value if isinstance(item, str))
    return ()
