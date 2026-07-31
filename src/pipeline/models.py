"""Typed models for the single-worker integration pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from crawler.result import FetchResult
from extractor.facade import ExtractionResult
from scoring.models import ScoringResult


class ProcessingStatus(StrEnum):
    """Terminal and retryable states for one candidate URL."""

    SUCCESS = "success"
    EXCLUDED = "excluded"
    DUPLICATE = "duplicate"
    ROBOTS_DENIED = "robots_denied"
    HTTP_403 = "http_403"
    HTTP_404 = "http_404"
    HTTP_429 = "http_429"
    HTTP_503 = "http_503"
    TIMEOUT = "timeout"
    TRANSPORT_ERROR = "transport_error"
    EXTRACTION_FAILED = "extraction_failed"
    SCORING_FAILED = "scoring_failed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PipelineLimits:
    """Safety and adoption limits for one condition run."""

    max_business_targets_per_condition: int = 500
    max_candidates_per_condition: int = 2000
    count_no_phone_as_business_target: bool = False

    def __post_init__(self) -> None:
        """Reject limits that could disable all forward progress."""
        if self.max_business_targets_per_condition < 1:
            raise ValueError("max_business_targets_per_condition must be positive")
        if self.max_candidates_per_condition < 1:
            raise ValueError("max_candidates_per_condition must be positive")

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> PipelineLimits:
        """Build limits from the operator-editable pipeline YAML mapping."""
        try:
            limits = config["limits"]
            count_no_phone = limits["count_no_phone_as_business_target"]
            if not isinstance(count_no_phone, bool):
                raise TypeError("count_no_phone_as_business_target must be boolean")
            return cls(
                int(limits["max_business_targets_per_condition"]),
                int(limits["max_candidates_per_condition"]),
                count_no_phone,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("pipeline limits configuration is incomplete") from exc


@dataclass(frozen=True, slots=True)
class SearchCondition:
    """One enabled geographic/industry search request."""

    prefecture: str
    municipality: str
    industry: str
    max_results: int
    enabled: bool = True

    def __post_init__(self) -> None:
        """Normalize required text and validate the result limit."""
        for field_name in ("prefecture", "municipality", "industry"):
            value = getattr(self, field_name).strip()
            if not value:
                raise ValueError(f"{field_name} must not be empty")
            object.__setattr__(self, field_name, value)
        if self.max_results < 1:
            raise ValueError("max_results must be positive")


@dataclass(frozen=True, slots=True)
class CandidateUrl:
    """Normalized search discovery metadata for one URL."""

    url: str
    query: str
    provider: str
    rank: int
    title: str
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize the candidate into JSON-compatible task payload data."""
        return {
            "url": self.url,
            "query": self.query,
            "provider": self.provider,
            "rank": self.rank,
            "title": self.title,
            "snippet": self.snippet,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> CandidateUrl:
        """Restore a candidate from a persisted progress payload."""
        return cls(
            str(value["url"]),
            str(value["query"]),
            str(value["provider"]),
            int(value["rank"]),
            str(value["title"]),
            str(value["snippet"]),
        )


@dataclass(frozen=True, slots=True)
class ProcessingContext:
    """IDs and immutable inputs needed to process one claimed candidate."""

    condition: SearchCondition
    candidate: CandidateUrl
    progress_id: int
    condition_id: int
    search_result_id: int


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Complete outcome for one candidate, including partial data on failure."""

    condition: SearchCondition
    candidate: CandidateUrl
    fetch_result: FetchResult | None
    extraction_result: ExtractionResult | None
    scoring_result: ScoringResult | None
    status: ProcessingStatus
    error_type: str | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime


@dataclass(frozen=True, slots=True)
class PipelineSummary:
    """Single-worker run totals and individual outcomes."""

    candidate_count: int
    processed_count: int
    business_target_count: int
    official_count: int
    excluded_count: int
    no_phone_count: int
    retry_count: int
    failed_count: int
    robots_denied_count: int
    status_counts: dict[ProcessingStatus, int]
    results: tuple[ProcessingResult, ...]

    @property
    def discovered(self) -> int:
        """Return the legacy alias for candidate count."""
        return self.candidate_count

    @property
    def processed(self) -> int:
        """Return the legacy alias for processed count."""
        return self.processed_count
