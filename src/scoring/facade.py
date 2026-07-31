"""Facade integrating domain, page, official, and business scoring."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from extractor.facade import ExtractionResult
from scoring.business_score import BusinessTargetScorer
from scoring.domain import DomainClassifier
from scoring.models import ScoringResult, SearchContext
from scoring.official_site import OfficialSiteScorer
from scoring.page_type import PageTypeClassifier


class ScoringFacade:
    """Produce one auditable official-site and business-target decision."""

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        exclude_domains_path: Path,
        industry_keywords_path: Path | None = None,
    ) -> None:
        self._config = config
        self._domain = DomainClassifier(exclude_domains_path)
        self._page = PageTypeClassifier()
        self._official = OfficialSiteScorer(config)
        self._business = BusinessTargetScorer(config)
        self._industry_keywords = _load_industry_keywords(industry_keywords_path)

    def score(
        self,
        extraction: ExtractionResult,
        url: str,
        context: SearchContext,
        html: str,
    ) -> ScoringResult:
        """Combine decisions without discarding any positive or negative reason."""
        domain = self._domain.classify(url)
        page_type = self._page.classify(url, html)
        enriched_context = _enrich_context(context, self._industry_keywords)
        official = self._official.score(
            extraction,
            url,
            html,
            enriched_context,
            page_type,
            domain_excluded=domain.is_excluded,
        )
        has_identity = any(
            (extraction.company_name, extraction.store_name, extraction.display_name)
        )
        business = self._business.score(
            official,
            page_type,
            domain_excluded=domain.is_excluded,
            has_phone=bool(extraction.phones),
            has_mobile=any(phone.kind == "mobile" for phone in extraction.phones),
            has_address=extraction.address is not None,
            has_identity=has_identity,
        )
        official_threshold = int(self._config["thresholds"]["official"])
        business_threshold = int(self._config["thresholds"]["business_target"])
        margin = int(self._config["thresholds"]["review_margin"])
        is_official = not domain.is_excluded and official.score >= official_threshold
        is_target = is_official and business.score >= business_threshold
        review = (
            not domain.is_excluded
            and (
                abs(official.score - official_threshold) <= margin
                or abs(business.score - business_threshold) <= margin
            )
        )
        reasons = list(dict.fromkeys((*official.reasons, *business.reasons)))
        if domain.reason:
            reasons.append(domain.reason)
        if not is_official and not domain.is_excluded:
            reasons.append(f"公式判定閾値未満: {official.score}/{official_threshold}")
        if is_official and not is_target:
            reasons.append(f"営業対象判定閾値未満: {business.score}/{business_threshold}")
        if is_target:
            reasons.append("公式サイトかつ営業対象の判定基準を満たす")
        return ScoringResult(
            official.score,
            business.score,
            is_official,
            is_target,
            review,
            tuple(reasons),
            tuple(dict.fromkeys((*official.positive_signals, *business.positive_signals))),
            tuple(dict.fromkeys((*official.negative_signals, *business.negative_signals))),
        )


def _load_industry_keywords(path: Path | None) -> dict[str, tuple[str, ...]]:
    if path is None:
        path = Path(__file__).resolve().parents[2] / "config/industry_keywords.yaml"
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        industries = content["industries"]
        return {
            str(value["display_name"]): tuple(str(item) for item in value["keywords"])
            for value in industries.values()
        }
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        raise ValueError(f"Unable to load industry keywords: {path}") from exc


def _enrich_context(
    context: SearchContext, keywords: Mapping[str, tuple[str, ...]]
) -> SearchContext:
    if context.industry_keywords:
        return context
    return SearchContext(
        context.prefecture,
        context.municipality,
        context.industry,
        keywords.get(context.industry, ()),
    )
