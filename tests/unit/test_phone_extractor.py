"""Step 5 phone extraction tests using local fixtures."""

from pathlib import Path

from bs4 import BeautifulSoup

from extractor.phone import PhoneExtractor

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def load(name: str) -> BeautifulSoup:
    """Load one synthetic page."""
    return BeautifulSoup((SAMPLES / name).read_text(encoding="utf-8"), "html.parser")


def test_excludes_fax_and_prioritizes_mobile_numbers() -> None:
    phones = PhoneExtractor().extract(load("extractor_full.html"))

    assert [phone.number for phone in phones] == ["090-1111-2222", "03-1234-5678"]
    assert phones[0].kind == "mobile"
    assert phones[0].usage == "reservation"
    assert phones[1].kind == "fixed"
    assert "03-1234-9999" not in {phone.number for phone in phones}


def test_recognizes_070_080_090_and_estimates_usage() -> None:
    phones = PhoneExtractor().extract(load("extractor_sections.html"))
    by_number = {phone.number: phone for phone in phones}

    assert by_number["080-2222-3333"].usage == "contact"
    assert by_number["070-4444-5555"].usage == "recruiting"
    assert by_number["03-1111-2222"].usage == "main"
    assert "03-1111-9999" not in by_number
