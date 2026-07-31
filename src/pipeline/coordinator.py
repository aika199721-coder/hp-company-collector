"""Single-worker coordinator connecting search, progress, and candidate processing."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit

from pipeline.errors import PipelinePayloadError
from pipeline.models import (
    CandidateUrl,
    PipelineLimits,
    PipelineSummary,
    ProcessingContext,
    ProcessingResult,
    ProcessingStatus,
    SearchCondition,
)
from pipeline.processor import CandidateProcessor
from search.providers.base import SearchResult
from search.query_builder import QueryBuilder, SearchCriteria
from storage.pipeline import PipelineRepository
from storage.progress import ProgressItem, ProgressStore


class SearchManagerLike(Protocol):
    """SearchManager boundary; providers remain hidden behind the manager."""

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Return normalized provider results."""


class PipelineCoordinator:
    """Discover, enqueue, atomically claim, and process candidates sequentially."""

    def __init__(
        self,
        query_builder: QueryBuilder,
        search_manager: SearchManagerLike,
        repository: PipelineRepository,
        progress: ProgressStore,
        processor: CandidateProcessor,
        *,
        limits: PipelineLimits | None = None,
        stop_requested: Callable[[], bool] | None = None,
    ) -> None:
        self._query_builder = query_builder
        self._search_manager = search_manager
        self._repository = repository
        self._progress = progress
        self._processor = processor
        self._limits = limits or PipelineLimits()
        self._stop_requested = stop_requested or (lambda: False)

    def run(self, condition: SearchCondition) -> PipelineSummary:
        """Execute one condition with a single worker and bounded processing count."""
        if not condition.enabled:
            return _summarize(0, (), self._limits)
        self._progress.resume_interrupted()
        condition_id = self._repository.create_condition(condition)
        self._repository.set_condition_status(condition_id, "processing")
        query = self._query_builder.build(
            SearchCriteria(condition.prefecture, condition.municipality, condition.industry)
        )
        candidate_limit = self._limits.max_candidates_per_condition
        search_results = self._search_manager.search(query, candidate_limit)
        for result in search_results:
            candidate = CandidateUrl(
                result.url,
                query,
                result.provider,
                result.rank,
                result.title,
                result.snippet,
            )
            search_result_id = self._repository.record_candidate(condition_id, candidate)
            payload = {
                "candidate": candidate.to_dict(),
                "condition": _condition_dict(condition),
                "condition_id": condition_id,
                "search_result_id": search_result_id,
            }
            self._progress.enqueue(_task_key(candidate.url), payload)

        outcomes: list[ProcessingResult] = []
        target_limit = min(
            condition.max_results,
            self._limits.max_business_targets_per_condition,
        )
        business_targets = 0
        while (
            len(outcomes) < candidate_limit
            and business_targets < target_limit
            and not self._stop_requested()
        ):
            item = self._progress.claim_next()
            if item is None:
                break
            try:
                context = _restore_context(item)
                self._progress.save_cursor(item.id, f"rank:{context.candidate.rank}")
                outcome = self._processor.process(context)
                outcomes.append(outcome)
                if _counts_as_business_target(outcome, self._limits):
                    business_targets += 1
            except Exception as exc:
                message = str(exc) or type(exc).__name__
                self._progress.fail(item.id, message)
                self._repository.save_error(None, item.id, "pipeline_error", message)
                try:
                    context = _restore_context(item)
                except (KeyError, TypeError, ValueError, PipelinePayloadError):
                    continue
                now = datetime.now(UTC)
                outcomes.append(
                    ProcessingResult(
                        context.condition,
                        context.candidate,
                        None,
                        None,
                        None,
                        ProcessingStatus.FAILED,
                        "pipeline_error",
                        message,
                        now,
                        now,
                    )
                )
        summary = _summarize(len(search_results), tuple(outcomes), self._limits)
        final_status = "pending" if summary.retry_count else "completed"
        self._repository.set_condition_status(condition_id, final_status)
        return summary


def _restore_context(item: ProgressItem) -> ProcessingContext:
    try:
        payload = item.payload
        condition_data = payload["condition"]
        condition = SearchCondition(
            str(condition_data["prefecture"]),
            str(condition_data["municipality"]),
            str(condition_data["industry"]),
            int(condition_data["max_results"]),
            bool(condition_data["enabled"]),
        )
        return ProcessingContext(
            condition,
            CandidateUrl.from_dict(payload["candidate"]),
            item.id,
            int(payload["condition_id"]),
            int(payload["search_result_id"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PipelinePayloadError(f"Invalid pipeline task payload: {item.id}") from exc


def _condition_dict(condition: SearchCondition) -> dict[str, object]:
    return {
        "prefecture": condition.prefecture,
        "municipality": condition.municipality,
        "industry": condition.industry,
        "max_results": condition.max_results,
        "enabled": condition.enabled,
    }


def _task_key(url: str) -> str:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if parts.scheme.lower() not in {"http", "https"} or not host:
        raise ValueError("candidate URL must be absolute HTTP(S)")
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", parts.query, ""))


def _counts_as_business_target(
    result: ProcessingResult, limits: PipelineLimits
) -> bool:
    scoring = result.scoring_result
    if scoring is None or not scoring.is_business_target:
        return False
    has_phone = bool(result.extraction_result and result.extraction_result.phones)
    return has_phone or limits.count_no_phone_as_business_target


def _summarize(
    candidates: int,
    outcomes: tuple[ProcessingResult, ...],
    limits: PipelineLimits,
) -> PipelineSummary:
    counts = Counter(result.status for result in outcomes)
    retry_statuses = {
        ProcessingStatus.HTTP_429,
        ProcessingStatus.HTTP_503,
        ProcessingStatus.TIMEOUT,
        ProcessingStatus.TRANSPORT_ERROR,
    }
    failed_statuses = {
        ProcessingStatus.HTTP_403,
        ProcessingStatus.HTTP_404,
        ProcessingStatus.EXTRACTION_FAILED,
        ProcessingStatus.SCORING_FAILED,
        ProcessingStatus.FAILED,
    }
    return PipelineSummary(
        candidates,
        len(outcomes),
        sum(_counts_as_business_target(result, limits) for result in outcomes),
        sum(
            bool(result.scoring_result and result.scoring_result.is_official)
            for result in outcomes
        ),
        counts[ProcessingStatus.EXCLUDED],
        sum(
            bool(result.extraction_result and not result.extraction_result.phones)
            for result in outcomes
        ),
        sum(counts[status] for status in retry_statuses),
        sum(counts[status] for status in failed_statuses),
        counts[ProcessingStatus.ROBOTS_DENIED],
        dict(counts),
        outcomes,
    )
