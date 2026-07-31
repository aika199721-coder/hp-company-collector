"""Step 3 company-name priority tests using local fixtures."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from extractor.company import CompanyNameExtractor

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def load(name: str) -> BeautifulSoup:
    """Load one synthetic page."""
    return BeautifulSoup((SAMPLES / name).read_text(encoding="utf-8"), "html.parser")


def test_company_section_precedes_jsonld_name_without_legal_name() -> None:
    value = CompanyNameExtractor().extract(load("extractor_full.html"))

    assert value is not None
    assert value.value == "株式会社本文候補"
    assert value.source == "company"


def test_company_section_precedes_ogp_title_and_h1() -> None:
    value = CompanyNameExtractor().extract(load("extractor_sections.html"))

    assert value is not None
    assert value.value == "医療法人ひかり会"
    assert value.source == "company"


def test_schema_precedes_other_visible_candidates() -> None:
    value = CompanyNameExtractor().extract(load("extractor_schema.html"))

    assert value is not None
    assert value.value == "株式会社青空"
    assert value.source == "schema"


@pytest.mark.parametrize(
    ("fixture", "expected", "source"),
    [
        ("company_footer.html", "株式会社フッター", "footer"),
        ("company_copyright.html", "株式会社コピーライト", "copyright"),
        ("company_ogp.html", "OGP店舗名", "ogp"),
        ("company_title.html", "タイトル店舗名", "title"),
        ("company_h1.html", "見出し店舗名", "h1"),
    ],
)
def test_fallback_sources_follow_required_order(
    fixture: str, expected: str, source: str
) -> None:
    """Exercise each fallback source with higher-priority sources absent."""
    value = CompanyNameExtractor().extract(load(fixture))

    assert value is not None
    assert value.value == expected
    assert value.source == source
