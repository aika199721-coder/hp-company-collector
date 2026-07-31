"""Step 2 schema.org parser tests using a local fixture."""

from pathlib import Path

from bs4 import BeautifulSoup

from extractor.schema import SchemaOrgParser

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def test_parses_microdata_entity_and_nested_address() -> None:
    soup = BeautifulSoup(
        (SAMPLES / "extractor_schema.html").read_text(encoding="utf-8"), "html.parser"
    )

    entities = SchemaOrgParser().parse(soup)

    assert len(entities) == 1
    assert entities[0].types == ("HairSalon",)
    assert entities[0].properties["name"] == "ヘアサロン青空"
    assert entities[0].properties["legalName"] == "株式会社青空"
    assert entities[0].properties["telephone"] == "03-9876-5432"
    assert entities[0].properties["address"]["addressLocality"] == "渋谷区"
