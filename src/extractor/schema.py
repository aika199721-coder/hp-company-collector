"""schema.org microdata parsing for supported business entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bs4 import BeautifulSoup, Tag

from extractor.jsonld import SUPPORTED_TYPES


@dataclass(frozen=True, slots=True)
class SchemaEntity:
    """Normalized schema.org microdata entity."""

    types: tuple[str, ...]
    properties: dict[str, Any]


class SchemaOrgParser:
    """Parse supported top-level schema.org microdata without network access."""

    def parse(self, soup: BeautifulSoup) -> list[SchemaEntity]:
        """Return supported item scopes and their direct/nested properties."""
        entities: list[SchemaEntity] = []
        for scope in soup.select("[itemscope][itemtype]"):
            if not isinstance(scope, Tag) or scope.find_parent(attrs={"itemscope": True}):
                continue
            types = _item_types(scope.get("itemtype"))
            if SUPPORTED_TYPES.intersection(types):
                entities.append(SchemaEntity(types, _properties(scope)))
        return entities


def _item_types(value: str | list[str] | None) -> tuple[str, ...]:
    values = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    return tuple(item.rstrip("/").rsplit("/", 1)[-1] for item in values)


def _properties(scope: Tag) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for node in scope.select("[itemprop]"):
        if not isinstance(node, Tag):
            continue
        parent_scope = node.find_parent(attrs={"itemscope": True})
        if parent_scope is not scope:
            continue
        name = node.get("itemprop")
        if not isinstance(name, str):
            continue
        if node.has_attr("itemscope"):
            properties[name] = _properties(node)
        else:
            properties[name] = _property_value(node)
    return properties


def _property_value(node: Tag) -> str:
    if node.name == "meta":
        value = node.get("content", "")
    elif node.name in {"a", "link"} and node.get("href"):
        value = str(node["href"])
        if value.lower().startswith("tel:"):
            value = value[4:]
    elif node.name in {"img", "source"} and node.get("src"):
        value = str(node["src"])
    else:
        value = node.get_text(" ", strip=True)
    return str(value).strip()
