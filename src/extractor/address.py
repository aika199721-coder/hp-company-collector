"""Japanese postal-address extraction with explicit source priority."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from extractor.jsonld import JsonLdParser
from extractor.models import ExtractedAddress

_POSTAL = re.compile(r"(?:〒\s*)?(\d{3})[-ー\N{MINUS SIGN}]?\s*(\d{4})")
_ADDRESS = re.compile(
    r"(北海道|東京都|(?:京都|大阪)府|.{2,3}県)"
    r"([^\s,、。]{1,12}?[市区町村])"
    r"([^\s,、。<>]{1,60})"
)


class AddressExtractor:
    """Extract one address using JSON-LD, company, access, footer, then body."""

    def __init__(
        self,
        jsonld_parser: JsonLdParser | None = None,
    ) -> None:
        self._jsonld = jsonld_parser or JsonLdParser()

    def extract(self, soup: BeautifulSoup) -> ExtractedAddress | None:
        """Return the highest-priority complete or partial Japanese address."""
        for entity in self._jsonld.parse(soup):
            address = _structured(entity.data.get("address"), "jsonld")
            if address:
                return address
        sections = (
            ("company", r"company|会社概要|法人概要"),
            ("access", r"access|アクセス"),
        )
        for source, pattern in sections:
            container = _section(soup, pattern)
            address = _from_text(container.get_text(" ", strip=True), source) if container else None
            if address:
                return address
        footer = soup.find("footer")
        if isinstance(footer, Tag):
            address = _from_text(footer.get_text(" ", strip=True), "footer")
            if address:
                return address
        return _from_text(soup.get_text(" ", strip=True), "body")


def _structured(value: Any, source: str) -> ExtractedAddress | None:
    if isinstance(value, str):
        return _from_text(value, source)
    if not isinstance(value, dict):
        return None
    postal = _normalize_postal(value.get("postalCode"))
    prefecture = _string(value.get("addressRegion"))
    municipality = _string(value.get("addressLocality"))
    street = _string(value.get("streetAddress"))
    address = "".join(part for part in (prefecture, municipality, street) if part)
    if not address:
        return None
    return ExtractedAddress(address, postal, prefecture, municipality, source)


def _from_text(text: str, source: str) -> ExtractedAddress | None:
    address_match = _ADDRESS.search(text)
    if not address_match:
        return None
    postal_match = _POSTAL.search(text)
    prefecture, municipality, remainder = address_match.groups()
    address = f"{prefecture}{municipality}{remainder}".strip()
    postal = f"{postal_match.group(1)}-{postal_match.group(2)}" if postal_match else None
    return ExtractedAddress(address, postal, prefecture, municipality, source)


def _section(soup: BeautifulSoup, pattern: str) -> Tag | None:
    regex = re.compile(pattern, re.IGNORECASE)
    node = soup.find(id=regex) or soup.find(class_=regex)
    if isinstance(node, Tag):
        return node
    heading = soup.find(re.compile(r"^h[1-6]$"), string=regex)
    if isinstance(heading, Tag):
        parent = heading.find_parent(["section", "article", "div"])
        return parent if isinstance(parent, Tag) else heading.parent
    return None


def _normalize_postal(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = _POSTAL.search(value)
    return f"{match.group(1)}-{match.group(2)}" if match else None


def _string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
