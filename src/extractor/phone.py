"""Japanese telephone extraction, FAX exclusion, classification, and use estimation."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from bs4 import BeautifulSoup

from extractor.jsonld import JsonLdParser
from extractor.models import ExtractedPhone
from extractor.schema import SchemaOrgParser

_SEPARATOR = r"[-ー\N{HYPHEN}\N{MINUS SIGN}\s]?"
_PHONE = re.compile(
    rf"(?<!\d)(0(?:[789]0|\d{{1,4}})){_SEPARATOR}"
    rf"(\d{{1,4}}){_SEPARATOR}(\d{{4}})(?!\d)"
)
_FAX = re.compile(r"(?:FAX|ファックス|ファクス)\s*[:\N{FULLWIDTH COLON}]?\s*$", re.IGNORECASE)


class PhoneExtractor:
    """Extract non-FAX Japanese numbers with mobile numbers ordered first."""

    def __init__(
        self,
        jsonld_parser: JsonLdParser | None = None,
        schema_parser: SchemaOrgParser | None = None,
    ) -> None:
        self._jsonld = jsonld_parser or JsonLdParser()
        self._schema = schema_parser or SchemaOrgParser()

    def extract(self, soup: BeautifulSoup) -> list[ExtractedPhone]:
        """Return de-duplicated 070/080/090 mobile and fixed numbers."""
        candidates: list[ExtractedPhone] = []
        for entity in self._jsonld.parse(soup):
            candidates.extend(_from_structured(entity.data.get("telephone"), "jsonld"))
            candidates.extend(_from_contact_points(entity.data.get("contactPoint")))
        for entity in self._schema.parse(soup):
            candidates.extend(_from_structured(entity.properties.get("telephone"), "schema"))

        normalized_text = unicodedata.normalize("NFKC", soup.get_text("\n", strip=True))
        for line in normalized_text.splitlines():
            for match in _PHONE.finditer(line):
                prefix = line[max(0, match.start() - 15) : match.start()]
                if _FAX.search(prefix):
                    continue
                candidates.append(_phone(match, _usage(line, match.start()), "body"))

        unique: dict[str, ExtractedPhone] = {}
        for candidate in candidates:
            current = unique.get(candidate.number)
            if current is None or _usage_priority(candidate.usage) > _usage_priority(current.usage):
                unique[candidate.number] = candidate
        return sorted(
            unique.values(), key=lambda item: (item.kind != "mobile", candidates.index(item))
        )


def _from_structured(value: Any, source: str) -> list[ExtractedPhone]:
    values = value if isinstance(value, list) else [value]
    phones: list[ExtractedPhone] = []
    for item in values:
        if not isinstance(item, str):
            continue
        match = _PHONE.search(unicodedata.normalize("NFKC", item))
        if match:
            phones.append(_phone(match, "main", source))
    return phones


def _from_contact_points(value: Any) -> list[ExtractedPhone]:
    points = value if isinstance(value, list) else [value]
    phones: list[ExtractedPhone] = []
    for point in points:
        if not isinstance(point, dict):
            continue
        contact_type = str(point.get("contactType", ""))
        usage = _usage(contact_type, len(contact_type))
        phones.extend(_from_structured_with_usage(point.get("telephone"), "jsonld", usage))
    return phones


def _from_structured_with_usage(value: Any, source: str, usage: str) -> list[ExtractedPhone]:
    phones = _from_structured(value, source)
    return [ExtractedPhone(item.number, item.kind, usage, item.source) for item in phones]


def _phone(match: re.Match[str], usage: str, source: str) -> ExtractedPhone:
    number = "-".join(match.groups())
    kind = "mobile" if match.group(1) in {"070", "080", "090"} else "fixed"
    return ExtractedPhone(number, kind, usage, source)


def _usage(line: str, position: int) -> str:
    context = line[max(0, position - 25) : position + 25]
    rules = (
        ("reservation", r"予約"),
        ("recruiting", r"採用|求人"),
        ("emergency", r"緊急|夜間"),
        ("contact", r"問い合わせ|問合せ|連絡"),
        ("main", r"代表|本社|TEL|電話"),
    )
    for usage, pattern in rules:
        if re.search(pattern, context, re.IGNORECASE):
            return usage
    return "unknown"


def _usage_priority(usage: str) -> int:
    return 0 if usage in {"unknown", "main"} else 1
