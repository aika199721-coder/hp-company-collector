"""Typed models shared by Phase 6 scoring components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchContext:
    """Original geography and industry search conditions."""

    prefecture: str
    municipality: str
    industry: str
    industry_keywords: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """A bounded score with auditable signals and human-readable reasons."""

    score: int
    positive_signals: tuple[str, ...]
    negative_signals: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScoringResult:
    """Combined official-site and business-target decision."""

    official_score: int
    business_score: int
    is_official: bool
    is_business_target: bool
    review_required: bool
    reasons: tuple[str, ...]
    positive_signals: tuple[str, ...]
    negative_signals: tuple[str, ...]
