"""Step 1 JSON-LD parser tests using local HTML fixtures."""

from pathlib import Path

from bs4 import BeautifulSoup

from extractor.jsonld import JsonLdParser

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def soup(name: str) -> BeautifulSoup:
    """Load a synthetic HTML fixture."""
    return BeautifulSoup((SAMPLES / name).read_text(encoding="utf-8"), "html.parser")


def test_parses_supported_type_and_nested_fields() -> None:
    entities = JsonLdParser().parse(soup("extractor_full.html"))

    assert len(entities) == 1
    assert entities[0].types == ("Restaurant",)
    assert entities[0].name == "株式会社さくらダイニング"
    assert entities[0].data["address"]["postalCode"] == "100-0001"


def test_handles_graph_type_lists_and_invalid_scripts() -> None:
    entities = JsonLdParser().parse(soup("extractor_jsonld_graph.html"))

    assert [entity.name for entity in entities] == [
        "医療法人テスト会",
        "テスト支店",
        "テスト美容室",
    ]
    assert entities[0].types == ("Organization", "MedicalBusiness")
