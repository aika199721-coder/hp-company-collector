"""Industry extraction from structured types and visible keyword evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping

from bs4 import BeautifulSoup, Tag

from extractor.jsonld import JsonLdParser
from extractor.models import ExtractedValue
from extractor.schema import SchemaOrgParser

_TYPE_INDUSTRIES = {
    "HairSalon": "美容業",
    "MedicalBusiness": "医療",
    "Restaurant": "飲食店",
}
_DEFAULT_KEYWORDS: Mapping[str, tuple[str, ...]] = {
    "飲食店": ("レストラン", "飲食店", "居酒屋", "食堂"),
    "美容業": ("美容室", "理容室", "ヘアサロン", "エステ"),
    "医療": ("クリニック", "医院", "病院", "診療"),
}
_ARTICLE_SIGNALS = ("観光", "旅行", "ニュース", "ランキング", "まとめ", "記事")


class IndustryExtractor:
    """Extract an industry from JSON-LD, schema.org, then visible keywords."""

    def __init__(
        self,
        keywords: Mapping[str, tuple[str, ...]] | None = None,
        jsonld_parser: JsonLdParser | None = None,
        schema_parser: SchemaOrgParser | None = None,
    ) -> None:
        self._keywords = keywords or _DEFAULT_KEYWORDS
        self._jsonld = jsonld_parser or JsonLdParser()
        self._schema = schema_parser or SchemaOrgParser()

    def extract(self, soup: BeautifulSoup) -> ExtractedValue | None:
        """Return the first structured type or strongest keyword industry."""
        for entity in self._jsonld.parse(soup):
            value = _from_types(entity.types)
            if value:
                return ExtractedValue(value, "jsonld")
        for entity in self._schema.parse(soup):
            value = _from_types(entity.types)
            if value:
                return ExtractedValue(value, "schema")

        for source, node in (("title", soup.title), ("h1", soup.find("h1"))):
            text = node.get_text(" ", strip=True) if node else ""
            value = _from_keywords(text, self._keywords, 1)
            if value:
                return ExtractedValue(value, source)
        section = _business_section(soup)
        if section:
            value = _from_keywords(section.get_text(" ", strip=True), self._keywords, 1)
            if value:
                return ExtractedValue(value, "business_section")
        heading_text = " ".join(
            node.get_text(" ", strip=True) for node in (soup.title, soup.find("h1")) if node
        )
        if any(signal in heading_text for signal in _ARTICLE_SIGNALS):
            return None
        text = soup.get_text(" ", strip=True)
        value = _from_keywords(text, self._keywords, 2)
        return ExtractedValue(value, "body") if value else None


def _from_keywords(
    text: str, keywords_by_industry: Mapping[str, tuple[str, ...]], minimum: int
) -> str | None:
    scores = {
        industry: sum(text.count(keyword) for keyword in keywords)
        for industry, keywords in keywords_by_industry.items()
    }
    if not scores:
        return None
    industry, score = max(scores.items(), key=lambda item: item[1])
    return industry if score >= minimum else None


def _business_section(soup: BeautifulSoup) -> Tag | None:
    pattern = re.compile(r"会社概要|店舗情報|サービス|事業内容|service|company", re.IGNORECASE)
    node = soup.find(id=pattern) or soup.find(class_=pattern)
    if isinstance(node, Tag):
        return node
    heading = soup.find(re.compile(r"^h[1-6]$"), string=pattern)
    if isinstance(heading, Tag):
        parent = heading.find_parent(["section", "article", "div"])
        return parent if isinstance(parent, Tag) else heading
    return None


def _from_types(types: tuple[str, ...]) -> str | None:
    return next((_TYPE_INDUSTRIES[item] for item in types if item in _TYPE_INDUSTRIES), None)
