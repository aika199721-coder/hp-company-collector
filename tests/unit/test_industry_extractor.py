"""Step 6 industry extraction tests using local fixtures."""

from pathlib import Path

from bs4 import BeautifulSoup

from extractor.industry import IndustryExtractor

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def load(name: str) -> BeautifulSoup:
    """Load one synthetic page."""
    return BeautifulSoup((SAMPLES / name).read_text(encoding="utf-8"), "html.parser")


def test_uses_jsonld_restaurant_type() -> None:
    industry = IndustryExtractor().extract(load("extractor_full.html"))

    assert industry is not None
    assert industry.value == "飲食店"
    assert industry.source == "jsonld"


def test_uses_schema_hair_salon_type() -> None:
    industry = IndustryExtractor().extract(load("extractor_schema.html"))

    assert industry is not None
    assert industry.value == "美容業"
    assert industry.source == "schema"


def test_uses_jsonld_medical_business_type() -> None:
    """Map the supported MedicalBusiness type."""
    industry = IndustryExtractor().extract(load("extractor_jsonld_graph.html"))

    assert industry is not None
    assert industry.value == "医療"
    assert industry.source == "jsonld"
