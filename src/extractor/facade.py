"""Single entry point coordinating Phase 5 extraction components."""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup

from extractor.address import AddressExtractor
from extractor.company import CompanyIdentityExtractor, CompanyNameExtractor
from extractor.industry import IndustryExtractor
from extractor.models import ExtractedAddress, ExtractedPhone, ExtractedValue
from extractor.phone import PhoneExtractor


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Combined extraction result with provenance retained on every value."""

    source_url: str
    company_name: ExtractedValue | None
    address: ExtractedAddress | None
    phones: tuple[ExtractedPhone, ...]
    industry: ExtractedValue | None
    store_name: ExtractedValue | None = None
    display_name: ExtractedValue | None = None


class ExtractorFacade:
    """Coordinate independent extractors over one parsed fixture/document."""

    def __init__(
        self,
        company: CompanyNameExtractor | None = None,
        address: AddressExtractor | None = None,
        phone: PhoneExtractor | None = None,
        industry: IndustryExtractor | None = None,
    ) -> None:
        self._company = company or CompanyNameExtractor()
        self._identity = CompanyIdentityExtractor(self._company)
        self._address = address or AddressExtractor()
        self._phone = phone or PhoneExtractor()
        self._industry = industry or IndustryExtractor()

    def extract(self, html: str, source_url: str) -> ExtractionResult:
        """Parse supplied HTML once and run extraction without any network access."""
        if not isinstance(html, str):
            raise TypeError("html must be a string")
        if not source_url.strip():
            raise ValueError("source_url must not be empty")
        soup = BeautifulSoup(html, "html.parser")
        identity = self._identity.extract(soup)
        return ExtractionResult(
            source_url=source_url,
            company_name=identity.company_name,
            store_name=identity.store_name,
            display_name=identity.display_name,
            address=self._address.extract(soup),
            phones=tuple(self._phone.extract(soup)),
            industry=self._industry.extract(soup),
        )
