"""Top-level collection workflow spanning configured search conditions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path

from application.config import ApplicationConfig
from application.factory import ApplicationComponents, ApplicationFactory
from application.input import InputIssue, InputMode, SearchConditionInput, SearchConditionReader
from application.shutdown import ShutdownController
from pipeline.models import PipelineLimits, PipelineSummary
from search.query_builder import QueryBuilder, SearchCriteria
from utils.logger import configure_application_logger


@dataclass(frozen=True, slots=True)
class CollectionOutcome:
    """Application result consumed by the CLI presentation boundary."""

    exit_code: int
    run_id: str | None = None
    summaries: tuple[PipelineSummary, ...] = ()
    issues: tuple[InputIssue, ...] = ()
    planned_queries: tuple[str, ...] = ()


class CollectionService:
    """Validate input, coordinate conditions, export, and persist run history."""

    def __init__(
        self,
        config: ApplicationConfig,
        factory: ApplicationFactory,
        shutdown: ShutdownController,
    ) -> None:
        self._config = config
        self._factory = factory
        self._shutdown = shutdown
        self._shutdown_handled = False

    def validate(self, input_path: Path | None = None) -> CollectionOutcome:
        """Validate input and build queries without opening SQLite or using HTTP."""
        document = self._read(input_path)
        builder = QueryBuilder()
        queries = tuple(
            builder.build(
                SearchCriteria(
                    r.condition.prefecture,
                    r.condition.municipality,
                    r.condition.industry,
                )
            )
            for r in document.conditions
            if r.condition.enabled
        )
        return CollectionOutcome(
            0 if not document.issues else 3,
            issues=document.issues,
            planned_queries=queries,
        )

    def run(
        self, command: str, *, input_path: Path | None = None, dry_run: bool = False
    ) -> CollectionOutcome:
        """Execute collect or resume and isolate failures by condition."""
        if dry_run:
            return self.validate(input_path)
        document = self._read(input_path)
        enabled = tuple(record for record in document.conditions if record.condition.enabled)
        components = self._factory.build()
        components.progress.resume_interrupted()
        actual_input = self._input_file(input_path)
        run_id = components.run_history.start(
            command,
            str(actual_input),
            str(self._config.config_file),
            len(enabled),
        )
        logger = configure_application_logger(
            self._config.log_path.parent,
            run_id,
            self._config.log_level,
        )
        logger.info("collection started command=%s conditions=%s", command, len(enabled))
        summaries: list[PipelineSummary] = []
        errors = len(document.issues)
        completed = 0
        try:
            for index, record in enumerate(enabled, start=1):
                if self._shutdown.is_requested():
                    return self._interrupt(components, run_id, summaries, completed, errors)
                components.run_history.start_condition(run_id, index)
                try:
                    limits = self._limits(
                        record.max_candidates,
                        record.count_no_phone_as_target,
                    )
                    coordinator = self._factory.coordinator_for(components, limits)
                    summary = coordinator.run(record.condition)
                    summaries.append(summary)
                    completed += 1
                    components.run_history.finish_condition(
                        run_id, index, "completed", _summary_dict(summary), None
                    )
                    if self._config.runtime.export_after_each_condition:
                        components.export_service.export_all()
                except Exception as exc:
                    errors += 1
                    logger.exception(
                        "condition failed",
                        extra={"condition_id": index, "processing_status": "failed"},
                    )
                    components.run_history.finish_condition(
                        run_id, index, "failed", {}, str(exc) or type(exc).__name__
                    )
                    if not self._config.runtime.continue_on_condition_error:
                        break
            if self._shutdown.is_requested():
                return self._interrupt(components, run_id, summaries, completed, errors)
            components.export_service.export_all()
            components.status_service.get_status()
            code = 3 if errors else 0
            components.run_history.finish(
                run_id,
                "partial" if errors else "completed",
                completed,
                sum(item.business_target_count for item in summaries),
                sum(item.processed_count for item in summaries),
                errors,
            )
            logger.info("collection finished status=%s", "partial" if errors else "completed")
            return CollectionOutcome(code, run_id, tuple(summaries), document.issues)
        except KeyboardInterrupt:
            self._shutdown.request("KeyboardInterrupt", "SIGINT")
            return self._interrupt(components, run_id, summaries, completed, errors)

    def _interrupt(
        self, components: ApplicationComponents, run_id: str, summaries: list[PipelineSummary],
        completed: int, errors: int
    ) -> CollectionOutcome:
        """Perform shutdown cleanup at most once."""
        if not self._shutdown_handled:
            self._shutdown_handled = True
            components.progress.resume_interrupted()
            if self._config.runtime.export_on_shutdown:
                components.export_service.export_all()
            reason = self._shutdown.reason or "shutdown requested"
            components.run_history.shutdown(run_id, reason, self._shutdown.signal_name)
            components.run_history.finish(
                run_id,
                "interrupted",
                completed,
                sum(item.business_target_count for item in summaries),
                sum(item.processed_count for item in summaries),
                errors,
                reason,
            )
        return CollectionOutcome(130, run_id, tuple(summaries))

    def _read(self, path: Path | None) -> SearchConditionInput:
        return SearchConditionReader(InputMode(self._config.runtime.input_mode)).read(
            self._input_file(path)
        )

    def _input_file(self, path: Path | None) -> Path:
        selected = path or self._config.input_path
        return selected / "search_conditions.csv" if selected.is_dir() else selected

    def _limits(self, candidates: int | None, no_phone: bool | None) -> PipelineLimits:
        limits = self._config.pipeline_limits
        return replace(
            limits,
            max_candidates_per_condition=candidates or limits.max_candidates_per_condition,
            count_no_phone_as_business_target=(
                limits.count_no_phone_as_business_target if no_phone is None else no_phone
            ),
        )


def _summary_dict(summary: PipelineSummary) -> dict[str, object]:
    """Serialize only aggregate values needed in run history."""
    value = asdict(summary)
    value.pop("results", None)
    value["status_counts"] = {str(key): count for key, count in summary.status_counts.items()}
    return value
