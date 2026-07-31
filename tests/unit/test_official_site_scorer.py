"""Phase 6 Step 3 OfficialSiteScorer tests with fake extracted data."""

from pathlib import Path

from extractor.facade import ExtractorFacade
from scoring.models import SearchContext
from scoring.official_site import OfficialSiteScorer
from scoring.page_type import PageTypeClassifier

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def test_scores_matching_official_fixture_highly(scoring_config: dict) -> None:
    html = (SAMPLES / "scoring_official.html").read_text(encoding="utf-8")
    extraction = ExtractorFacade().extract(html, "https://sakura-kensetsu.example/")
    page_type = PageTypeClassifier().classify(extraction.source_url, html)

    result = OfficialSiteScorer(scoring_config).score(
        extraction,
        extraction.source_url,
        html,
        SearchContext("東京都", "千代田区", "建設業", ("工務店", "リフォーム")),
        page_type,
        domain_excluded=False,
    )

    assert result.score >= scoring_config["thresholds"]["official"]
    assert "phone" in result.positive_signals
    assert "industry_match" in result.positive_signals
    assert result.negative_signals == ()
