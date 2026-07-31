"""Explicit confirmation and orchestration for bounded live validation."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from application.collection import CollectionOutcome, CollectionService
from application.config import ApplicationConfig
from application.factory import ApplicationFactory
from application.input import InputMode, SearchConditionReader
from application.shutdown import ShutdownController
from live.audit import HttpAuditRepository
from live.config import LiveValidationConfig
from live.http import BoundedHttpClient
from live.report import LiveReportService
from live.safety import LiveSafetyFetcher
from live.search import BoundedSearchManager
from pipeline.models import PipelineLimits
from storage.sqlite import Database


@dataclass(frozen=True, slots=True)
class LiveCheckOutcome:
    """Result distinguishing declined checks from completed collection runs."""

    started: bool
    exit_code: int
    collection: CollectionOutcome | None = None


class LiveValidationService:
    """Require consent, apply hard ceilings, and generate review artifacts."""

    def __init__(
        self,
        application: ApplicationConfig,
        live: LiveValidationConfig,
        *,
        input_func: Callable[[str], str] = input,
        interactive: Callable[[], bool] = lambda: sys.stdin.isatty(),
    ) -> None:
        self._application = application
        self._live = live
        self._input = input_func
        self._interactive = interactive

    def preview(self) -> tuple[str, ...]:
        """Return the mandatory pre-communication Japanese safety summary."""
        document = SearchConditionReader(InputMode.STRICT).read(self._input_file())
        enabled = [record.condition for record in document.conditions if record.condition.enabled]
        if len(enabled) > self._live.max_conditions:
            raise ValueError("live-checkは有効な検索条件1件だけで実行してください")
        condition = enabled[0] if enabled else None
        label = (
            f"{condition.prefecture} {condition.municipality} {condition.industry}"
            if condition
            else "有効な検索条件なし"
        )
        return (
            f"検索条件: {label}",
            f"営業対象上限: {self._live.max_business_targets}",
            f"候補処理上限: {self._live.max_candidates}",
            f"同一ドメイン待機時間: {self._live.delay_seconds}秒",
            "Playwright: 無効",
            "外部通信を行い、robots.txtを尊重します。",
        )

    def run(self, *, yes: bool = False) -> LiveCheckOutcome:
        """Start only after interactive Y or explicit non-interactive --yes."""
        self.preview()
        if not yes:
            if not self._interactive():
                return LiveCheckOutcome(False, 2)
            if self._input("実通信テストを開始しますか? [Y/N]: ").strip().upper() != "Y":
                return LiveCheckOutcome(False, 0)
        database = Database(self._application.database_path)
        database.initialize()
        audit_run_id = f"live-{uuid4().hex}"
        audit = HttpAuditRepository(database)
        safe_config = replace(
            self._application,
            request_timeout_seconds=self._live.timeout_seconds,
            per_domain_delay_seconds=self._live.delay_seconds,
            max_redirects=self._live.max_redirects,
            playwright_enabled=False,
            pipeline_limits=PipelineLimits(
                self._live.max_business_targets,
                self._live.max_candidates,
                self._application.pipeline_limits.count_no_phone_as_business_target,
            ),
        )

        def decorate(fetcher: object) -> LiveSafetyFetcher:
            return LiveSafetyFetcher(fetcher, self._live, audit, audit_run_id)

        def decorate_search(manager: object) -> BoundedSearchManager:
            return BoundedSearchManager(manager, self._live.max_results_per_query)

        shutdown = ShutdownController()
        factory = ApplicationFactory(
            safe_config,
            overrides={
                "database": database,
                "http_client": BoundedHttpClient(self._live.max_response_bytes),
                "fetcher_decorator": decorate,
                "search_manager_decorator": decorate_search,
            },
            shutdown=shutdown,
        )
        outcome = CollectionService(safe_config, factory, shutdown).run("live-check")
        LiveReportService(database).export(
            safe_config.output_path / "live_validation_report.xlsx",
            safe_config.input_path / "live_review.csv",
            audit_run_id,
        )
        return LiveCheckOutcome(True, outcome.exit_code, outcome)

    def _input_file(self) -> Path:
        path = self._application.input_path
        return path / "search_conditions.csv" if path.is_dir() else path
