"""Industry extraction from structured types and visible keyword evidence."""

from __future__ import annotations

from collections.abc import Mapping

from bs4 import BeautifulSoup

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

        text = soup.get_text(" ", strip=True)
        scores = {
            industry: sum(text.count(keyword) for keyword in keywords)
            for industry, keywords in self._keywords.items()
        }
        if not scores:
            return None
        industry, score = max(scores.items(), key=lambda item: item[1])
        return ExtractedValue(industry, "body") if score > 0 else None


def _from_types(types: tuple[str, ...]) -> str | None:
    return next((_TYPE_INDUSTRIES[item] for item in types if item in _TYPE_INDUSTRIES), None)
