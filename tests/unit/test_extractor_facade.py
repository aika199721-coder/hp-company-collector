"""Step 7 ExtractorFacade integration tests using a local HTML fixture."""

from pathlib import Path

from extractor.facade import ExtractorFacade

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def test_extracts_normalized_fields_without_network_access() -> None:
    html = (SAMPLES / "extractor_full.html").read_text(encoding="utf-8")

    result = ExtractorFacade().extract(html, source_url="https://fixture.invalid/about")

    assert result.company_name is not None
    assert result.company_name.value == "株式会社本文候補"
    assert result.address is not None
    assert result.address.prefecture == "東京都"
    assert result.phones[0].number == "090-1111-2222"
    assert result.industry is not None
    assert result.industry.value == "飲食店"
    assert result.source_url == "https://fixture.invalid/about"
