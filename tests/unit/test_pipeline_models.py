"""Phase 7 Step 1 pipeline model tests."""

from pathlib import Path

import pytest
import yaml

from pipeline.models import CandidateUrl, PipelineLimits, ProcessingStatus, SearchCondition


def test_search_condition_validates_and_normalizes() -> None:
    condition = SearchCondition(" 東京都 ", "千代田区", "建設業", 5, True)

    assert condition.prefecture == "東京都"
    assert condition.max_results == 5

    with pytest.raises(ValueError, match="max_results"):
        SearchCondition("東京都", "千代田区", "建設業", 0)


def test_candidate_and_status_are_typed() -> None:
    candidate = CandidateUrl("https://example.jp", "query", "fake", 1, "title", "snippet")

    assert candidate.provider == "fake"
    assert ProcessingStatus.SUCCESS.value == "success"
    assert ProcessingStatus.ROBOTS_DENIED.value == "robots_denied"


def test_pipeline_limits_load_from_operator_config() -> None:
    path = Path(__file__).resolve().parents[2] / "config/pipeline.yaml"
    limits = PipelineLimits.from_config(yaml.safe_load(path.read_text(encoding="utf-8")))

    assert limits.max_business_targets_per_condition == 500
    assert limits.max_candidates_per_condition == 2000
    assert limits.count_no_phone_as_business_target is False
