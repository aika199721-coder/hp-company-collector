"""Phase 5 reinforcement tests requested before Phase 6 implementation."""

from pathlib import Path

from bs4 import BeautifulSoup

from extractor.company import CompanyIdentityExtractor, CompanyNameExtractor
from extractor.facade import ExtractorFacade
from extractor.jsonld import JsonLdParser
from extractor.phone import PhoneExtractor

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def load() -> BeautifulSoup:
    """Load the synthetic mixed-identity fixture."""
    return BeautifulSoup(
        (SAMPLES / "extractor_reinforcement.html").read_text(encoding="utf-8"),
        "html.parser",
    )


def test_mixed_jsonld_uses_legal_name_and_keeps_identity_fields_separate() -> None:
    soup = load()
    entities = JsonLdParser().parse(soup)
    identity = CompanyIdentityExtractor().extract(soup)

    assert [entity.types for entity in entities] == [("Organization",), ("LocalBusiness",)]
    assert CompanyNameExtractor().extract(soup).value == "株式会社さくら運営"
    assert identity.company_name.value == "株式会社さくら運営"
    assert identity.store_name.value == "さくら新宿店"
    assert identity.display_name.value == "さくらブランド"


def test_phone_arrays_contact_points_full_width_fax_and_mobile_usage() -> None:
    phones = PhoneExtractor().extract(load())
    by_number = {phone.number: phone for phone in phones}

    assert by_number["090-1234-5678"].usage == "reservation"
    assert by_number["080-2222-3333"].usage == "reservation"
    assert by_number["070-3333-4444"].usage == "recruiting"
    assert by_number["080-5555-6666"].usage == "emergency"
    assert "03-1111-9999" not in by_number


def test_multiple_addresses_choose_first_high_priority_store() -> None:
    html = (SAMPLES / "extractor_reinforcement.html").read_text(encoding="utf-8")
    result = ExtractorFacade().extract(html, "https://fixture.invalid/")

    assert result.address is not None
    assert result.address.address == "東京都新宿区新宿1-1-1"
    assert result.company_name.value == "株式会社さくら運営"
    assert result.store_name.value == "さくら新宿店"
    assert result.display_name.value == "さくらブランド"


def test_generic_navigation_labels_are_not_names_and_copyright_is_cleaned() -> None:
    identity = CompanyIdentityExtractor().extract(load())

    values = {item.value for item in identity.values() if item is not None}
    assert values.isdisjoint({"アクセス", "会社概要", "お問い合わせ"})
    assert identity.company_name.value == "株式会社さくら運営"
