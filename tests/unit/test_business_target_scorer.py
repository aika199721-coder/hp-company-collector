"""Phase 6 Step 4 BusinessTargetScorer tests."""

from scoring.business_score import BusinessTargetScorer
from scoring.models import ScoreBreakdown
from scoring.page_type import PageType


def test_portal_is_hard_excluded_even_with_phone(scoring_config: dict) -> None:
    official = ScoreBreakdown(72, ("phone", "address"), ("portal",), ("電話あり",))

    result = BusinessTargetScorer(scoring_config).score(
        official, PageType.PORTAL, domain_excluded=True, has_phone=True
    )

    assert result.score == 0
    assert "excluded_domain" in result.negative_signals
    assert any("除外" in reason for reason in result.reasons)
