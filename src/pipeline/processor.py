"""Single-candidate pipeline processor with isolated failure handling."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Protocol

from crawler.result import FetchResult
from extractor.facade import ExtractionResult
from pipeline.models import ProcessingContext, ProcessingResult, ProcessingStatus
from scoring.models import ScoringResult, SearchContext
from storage.pipeline import PipelineRepository
from storage.progress import ProgressStore


class FetcherLike(Protocol):
    """Fetcher boundary used by the pipeline."""

    def fetch(self, url: str) -> FetchResult:
        """Return raw transport data."""


class ExtractorLike(Protocol):
    """ExtractorFacade boundary used by the pipeline."""

    def extract(self, html: str, source_url: str) -> ExtractionResult:
        """Extract normalized company information."""


class ScorerLike(Protocol):
    """ScoringFacade boundary used by the pipeline."""

    def score(
        self, extraction: ExtractionResult, url: str, context: SearchContext, html: str
    ) -> ScoringResult:
        """Return official and business decisions."""


class CandidateProcessor:
    """Run one atomically claimed candidate through transport, extraction, and scoring."""

    def __init__(
        self,
        fetcher: FetcherLike,
        extractor: ExtractorLike,
        scorer: ScorerLike | None,
        repository: PipelineRepository,
        progress: ProgressStore,
        *,
        retry_delay_seconds: int = 300,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._fetcher = fetcher
        self._extractor = extractor
        self._scorer = scorer
        self._repository = repository
        self._progress = progress
        self._retry_delay = retry_delay_seconds
        self._clock = clock

    def process(self, context: ProcessingContext) -> ProcessingResult:
        """Process one URL and convert every expected failure to a persisted state."""
        started = self._clock()
        paused_until = self._repository.domain_pause_until(context.candidate.url)
        if paused_until:
            pause = datetime.strptime(paused_until, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
            if pause > started:
                self._progress.retry(
                    context.progress_id, paused_until, "domain_paused"
                )
                return self._result(
                    context,
                    ProcessingStatus.HTTP_429,
                    started,
                    error_type="domain_paused",
                    error_message=f"domain paused until {paused_until}",
                )
        terminal = self._repository.terminal_status(context.candidate.url)
        if terminal is not None:
            self._progress.complete(context.progress_id)
            return self._result(context, ProcessingStatus.DUPLICATE, started)

        fetch = self._fetcher.fetch(context.candidate.url)
        transport = self._transport_state(fetch)
        if transport is not None:
            status, retryable = transport
            page_id = self._repository.save_page(context.candidate.url, fetch, status)
            if retryable:
                self._schedule_retry(context, fetch, status)
            else:
                self._progress.complete(context.progress_id)
            error_type = None if status is ProcessingStatus.ROBOTS_DENIED else status.value
            if error_type:
                self._repository.save_error(
                    page_id, context.progress_id, error_type, fetch.error or ""
                )
            return self._result(
                context,
                status,
                started,
                fetch=fetch,
                error_type=error_type,
                error_message=fetch.error,
            )

        page_id = self._repository.save_page(
            context.candidate.url, fetch, ProcessingStatus.SUCCESS
        )
        try:
            extraction = self._extractor.extract(fetch.text, fetch.final_url)
        except Exception as exc:
            return self._failure(
                context,
                fetch,
                page_id,
                ProcessingStatus.EXTRACTION_FAILED,
                "extraction_error",
                exc,
                started,
            )
        self._repository.save_extraction(page_id, extraction)
        if self._scorer is None:
            return self._failure(
                context,
                fetch,
                page_id,
                ProcessingStatus.SCORING_FAILED,
                "scoring_unavailable",
                RuntimeError("scorer is not configured"),
                started,
                extraction,
            )
        try:
            search_context = SearchContext(
                context.condition.prefecture,
                context.condition.municipality,
                context.condition.industry,
            )
            scoring = self._scorer.score(
                extraction, fetch.final_url, search_context, fetch.text
            )
        except Exception as exc:
            return self._failure(
                context,
                fetch,
                page_id,
                ProcessingStatus.SCORING_FAILED,
                "scoring_error",
                exc,
                started,
                extraction,
            )
        self._repository.save_scoring(page_id, scoring)
        status = (
            ProcessingStatus.SUCCESS
            if scoring.is_business_target
            else ProcessingStatus.EXCLUDED
        )
        self._repository.save_page(context.candidate.url, fetch, status)
        self._progress.complete(context.progress_id)
        return self._result(
            context, status, started, fetch=fetch, extraction=extraction, scoring=scoring
        )

    def _transport_state(
        self, fetch: FetchResult
    ) -> tuple[ProcessingStatus, bool] | None:
        if fetch.error == "robots_denied":
            return ProcessingStatus.ROBOTS_DENIED, False
        if fetch.error == "timeout":
            return ProcessingStatus.TIMEOUT, True
        if fetch.error:
            return ProcessingStatus.TRANSPORT_ERROR, True
        statuses = {
            403: (ProcessingStatus.HTTP_403, False),
            404: (ProcessingStatus.HTTP_404, False),
            429: (ProcessingStatus.HTTP_429, True),
            503: (ProcessingStatus.HTTP_503, True),
        }
        if fetch.status_code in statuses:
            return statuses[fetch.status_code]
        if fetch.status_code is None or not 200 <= fetch.status_code < 300:
            return ProcessingStatus.FAILED, False
        return None

    def _schedule_retry(
        self,
        context: ProcessingContext,
        fetch: FetchResult,
        status: ProcessingStatus,
    ) -> None:
        delay = self._retry_delay
        if status is ProcessingStatus.HTTP_429:
            retry_after = fetch.headers.get("retry-after")
            try:
                delay = max(delay, int(retry_after or delay))
            except ValueError:
                try:
                    retry_date = parsedate_to_datetime(retry_after or "")
                    delay = max(delay, round((retry_date - self._clock()).total_seconds()))
                except (TypeError, ValueError, OverflowError):
                    delay = self._retry_delay
        available = self._clock() + timedelta(seconds=delay)
        timestamp = available.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
        self._progress.retry(context.progress_id, timestamp, status.value)
        self._repository.pause_domain(context.candidate.url, available, status.value)

    def _failure(
        self,
        context: ProcessingContext,
        fetch: FetchResult,
        page_id: int,
        status: ProcessingStatus,
        error_type: str,
        error: Exception,
        started: datetime,
        extraction: ExtractionResult | None = None,
    ) -> ProcessingResult:
        message = str(error) or type(error).__name__
        self._repository.save_page(context.candidate.url, fetch, status)
        self._repository.save_error(page_id, context.progress_id, error_type, message)
        self._progress.fail(context.progress_id, message)
        return self._result(
            context,
            status,
            started,
            fetch=fetch,
            extraction=extraction,
            error_type=error_type,
            error_message=message,
        )

    def _result(
        self,
        context: ProcessingContext,
        status: ProcessingStatus,
        started: datetime,
        *,
        fetch: FetchResult | None = None,
        extraction: ExtractionResult | None = None,
        scoring: ScoringResult | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> ProcessingResult:
        return ProcessingResult(
            context.condition,
            context.candidate,
            fetch,
            extraction,
            scoring,
            status,
            error_type,
            error_message,
            started,
            self._clock(),
        )
