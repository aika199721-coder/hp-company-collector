"""Phase 6 Step 5 ScoringFacade integration tests using fixtures only."""

from pathlib import Path

from extractor.facade import ExtractorFacade
from scoring.facade import ScoringFacade
from scoring.models import SearchContext

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def test_integrates_official_and_business_decisions(scoring_facade: ScoringFacade) -> None:
    html = (SAMPLES / "scoring_official.html").read_text(encoding="utf-8")
    extraction = ExtractorFacade().extract(html, "https://sakura-kensetsu.example/")

    result = scoring_facade.score(
        extraction,
        extraction.source_url,
        SearchContext("東京都", "千代田区", "建設業", ("工務店", "リフォーム")),
        html,
    )

    assert result.official_score >= 60
    assert result.business_score >= 55
    assert result.is_official is True
    assert result.is_business_target is True
    assert result.review_required is False
    assert result.reasons
    assert result.positive_signals


def test_portal_fixture_is_never_business_target(scoring_facade: ScoringFacade) -> None:
    html = (SAMPLES / "scoring_portal.html").read_text(encoding="utf-8")
    extraction = ExtractorFacade().extract(html, "https://itp.ne.jp/ranking")

    result = scoring_facade.score(
        extraction,
        extraction.source_url,
        SearchContext("東京都", "千代田区", "建設業", ("工務店",)),
        html,
    )

    assert result.is_business_target is False
    assert result.business_score == 0
    assert result.negative_signals
    assert any("除外" in reason for reason in result.reasons)
