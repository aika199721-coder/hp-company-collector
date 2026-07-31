"""Business-target scoring with hard exclusions and explicit reasons."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from scoring.models import ScoreBreakdown
from scoring.page_type import PageType


class BusinessTargetScorer:
    """Score sales-target quality while preserving mandatory exclusions."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        try:
            self._weights = config["weights"]["business"]
            self._hard_excluded = {
                PageType(value) for value in config["hard_excluded_page_types"]
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("business scoring configuration is incomplete") from exc

    def score(
        self,
        official: ScoreBreakdown,
        page_type: PageType,
        *,
        domain_excluded: bool,
        has_phone: bool,
        has_mobile: bool = False,
        has_address: bool = False,
        has_identity: bool = False,
    ) -> ScoreBreakdown:
        """Return a business score; portal/job exclusions override contact data."""
        positives = list(official.positive_signals)
        negatives = list(official.negative_signals)
        reasons = list(official.reasons)
        if domain_excluded or page_type in self._hard_excluded:
            signal = (
                "excluded_domain"
                if domain_excluded
                else f"excluded_page_type:{page_type.value}"
            )
            negatives.append(signal)
            reasons.append("ポータル・求人・記事・電話帳等の除外対象")
            return ScoreBreakdown(0, tuple(positives), tuple(negatives), tuple(reasons))

        score = official.score * float(self._weights["official_factor"])
        additions = (
            (has_phone, "business_phone", "phone", "営業連絡可能な電話番号"),
            (has_mobile, "business_mobile", "mobile_phone", "携帯電話を確認"),
            (has_address, "business_address", "address", "所在地を確認"),
            (has_identity, "business_identity", "identity", "営業先名称を確認"),
            (
                page_type in {PageType.OFFICIAL_HOME, PageType.STORE, PageType.COMPANY},
                "business_page",
                "official_or_store_page",
                "公式・店舗・会社ページ",
            ),
        )
        for enabled, signal, weight, reason in additions:
            if enabled:
                score += float(self._weights[weight])
                positives.append(signal)
                reasons.append(reason)
        return ScoreBreakdown(
            max(0, min(100, round(score))),
            tuple(dict.fromkeys(positives)),
            tuple(dict.fromkeys(negatives)),
            tuple(dict.fromkeys(reasons)),
        )
