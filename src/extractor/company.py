"""Company-name extraction with explicit source priority."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from extractor.jsonld import JsonLdParser
from extractor.models import ExtractedValue
from extractor.schema import SchemaOrgParser

_LEGAL_NAME = re.compile(
    r"(?:株式会社|有限会社|合同会社|医療法人(?:社団|財団)?|学校法人|社会福祉法人)"
    r"[\w\u3000-\u30ff\u3400-\u9fff・ー]{1,40}"
)
_GENERIC_NAMES = frozenset({"アクセス", "会社概要", "お問い合わせ", "店舗情報", "ホーム"})


@dataclass(frozen=True, slots=True)
class CompanyIdentity:
    """Separate legal company, store, and display names."""

    company_name: ExtractedValue | None
    store_name: ExtractedValue | None
    display_name: ExtractedValue | None

    def values(self) -> tuple[ExtractedValue | None, ...]:
        """Return all identity fields in stable order."""
        return self.company_name, self.store_name, self.display_name


class CompanyNameExtractor:
    """Extract one company/display name using the required priority order."""

    def __init__(
        self,
        jsonld_parser: JsonLdParser | None = None,
        schema_parser: SchemaOrgParser | None = None,
    ) -> None:
        self._jsonld = jsonld_parser or JsonLdParser()
        self._schema = schema_parser or SchemaOrgParser()

    def extract(self, soup: BeautifulSoup) -> ExtractedValue | None:
        """Extract the legal company name using the required priority."""
        entities = self._jsonld.parse(soup)
        for entity in entities:
            legal_name = _string_value(entity.data.get("legalName"))
            if legal_name:
                return ExtractedValue(legal_name, "jsonld_legal_name")
        for entity in self._schema.parse(soup):
            legal_name = _string_value(entity.properties.get("legalName"))
            if legal_name is None and "Organization" in entity.types:
                legal_name = _string_value(entity.properties.get("name"))
            if legal_name and not _is_generic(legal_name):
                return ExtractedValue(legal_name, "schema")
        company = _company_section_name(soup)
        if company:
            return ExtractedValue(company, "company")
        for entity in entities:
            if entity.name:
                return ExtractedValue(entity.name, "jsonld")

        extractors: tuple[tuple[str, Callable[[], str | None]], ...] = (
            ("copyright", lambda: _copyright_name(soup)),
            ("footer", lambda: _footer_name(soup)),
            ("ogp", lambda: _meta(soup, "og:site_name")),
            ("title", lambda: _title(soup)),
            ("h1", lambda: _tag_text(soup.find("h1"))),
        )
        for source, extractor in extractors:
            value = extractor()
            if value:
                return ExtractedValue(value, source)
        return None


class CompanyIdentityExtractor:
    """Keep legal company, store, and display identities separate."""

    def __init__(self, company_extractor: CompanyNameExtractor | None = None) -> None:
        self._company = company_extractor or CompanyNameExtractor()
        self._jsonld = self._company._jsonld
        self._schema = self._company._schema

    def extract(self, soup: BeautifulSoup) -> CompanyIdentity:
        """Extract the three identity fields without collapsing their meanings."""
        store_name: ExtractedValue | None = None
        display_name: ExtractedValue | None = None
        for entity in self._jsonld.parse(soup):
            if "LocalBusiness" in entity.types or any(
                item in entity.types for item in ("HairSalon", "MedicalBusiness", "Restaurant")
            ):
                if entity.name and not _is_generic(entity.name):
                    store_name = ExtractedValue(entity.name, "jsonld")
                alternate = _string_value(entity.data.get("alternateName"))
                if alternate and not _is_generic(alternate):
                    display_name = ExtractedValue(alternate, "jsonld")
                break
        if store_name is None:
            for entity in self._schema.parse(soup):
                name = _string_value(entity.properties.get("name"))
                if name and not _is_generic(name):
                    store_name = ExtractedValue(name, "schema")
                    break
        display_name = display_name or store_name
        return CompanyIdentity(self._company.extract(soup), store_name, display_name)


def _footer_name(soup: BeautifulSoup) -> str | None:
    footer = soup.find("footer")
    if not isinstance(footer, Tag):
        return None
    text = footer.get_text(" ", strip=True).split("©", 1)[0]
    return _legal_name(text)


def _copyright_name(soup: BeautifulSoup) -> str | None:
    text = soup.get_text(" ", strip=True)
    for marker in ("©", "Copyright", "copyright"):
        if marker in text:
            return _legal_name(text.split(marker, 1)[1][:100])
    return None


def _company_section_name(soup: BeautifulSoup) -> str | None:
    keywords = re.compile(r"会社概要|法人概要|運営会社|店舗情報")
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        if not keywords.search(heading.get_text(" ", strip=True)):
            continue
        container = heading.find_parent(["section", "article", "div"]) or heading.parent
        if isinstance(container, Tag):
            text = container.get_text(" ", strip=True)
            legal = _legal_name(text)
            if legal:
                return legal
            label = container.find(string=re.compile(r"法人名|会社名|運営会社"))
            if label and isinstance(label.parent, Tag):
                sibling = label.parent.find_next_sibling()
                value = _tag_text(sibling)
                if value:
                    return value
    return None


def _legal_name(text: str) -> str | None:
    match = _LEGAL_NAME.search(text)
    return match.group(0).strip() if match else None


def _meta(soup: BeautifulSoup, property_name: str) -> str | None:
    node = soup.find("meta", attrs={"property": property_name})
    if isinstance(node, Tag):
        value = node.get("content")
        return str(value).strip() if value else None
    return None


def _title(soup: BeautifulSoup) -> str | None:
    value = _tag_text(soup.title)
    if not value:
        return None
    return re.split(r"\s*[|\N{FULLWIDTH VERTICAL LINE}]\s*", value, maxsplit=1)[0]


def _tag_text(node: object) -> str | None:
    if isinstance(node, Tag):
        value = node.get_text(" ", strip=True)
        return value if value and not _is_generic(value) else None
    return None


def _string_value(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _is_generic(value: str) -> bool:
    return value.strip() in _GENERIC_NAMES
