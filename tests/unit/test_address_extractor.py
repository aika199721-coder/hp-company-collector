"""Step 4 address priority tests using local fixtures."""

from pathlib import Path

from bs4 import BeautifulSoup

from extractor.address import AddressExtractor

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def load(name: str) -> BeautifulSoup:
    """Load one synthetic page."""
    return BeautifulSoup((SAMPLES / name).read_text(encoding="utf-8"), "html.parser")


def test_jsonld_address_has_highest_priority() -> None:
    address = AddressExtractor().extract(load("extractor_full.html"))

    assert address is not None
    assert address.postal_code == "100-0001"
    assert address.address == "東京都千代田区千代田1-1"
    assert address.source == "jsonld"


def test_access_section_is_used_before_document_body() -> None:
    address = AddressExtractor().extract(load("extractor_sections.html"))

    assert address is not None
    assert address.postal_code == "160-0022"
    assert address.address == "東京都新宿区新宿3-4-5"
    assert address.source == "access"


def test_company_section_precedes_access_and_footer() -> None:
    """Honor the required visible-address source priority."""
    address = AddressExtractor().extract(load("address_priority.html"))

    assert address is not None
    assert address.address == "大阪府大阪市北区梅田1-1-1"
    assert address.source == "company"
