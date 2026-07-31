"""Phase 9 command-line boundary for collection and local administration."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parent
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from __version__ import __version__  # noqa: E402
from application.collection import CollectionService  # noqa: E402
from application.compatibility import check_runtime  # noqa: E402
from application.config import (  # noqa: E402
    ApplicationConfigError,
    ApplicationConfigLoader,
)
from application.factory import ApplicationFactory  # noqa: E402
from application.input import InputValidationError  # noqa: E402
from application.shutdown import ShutdownController  # noqa: E402
from export.service import ExportService  # noqa: E402
from live.config import LiveValidationConfig  # noqa: E402
from live.report import LiveReportService  # noqa: E402
from live.review import ManualReviewService  # noqa: E402
from live.service import LiveValidationService  # noqa: E402
from status.models import StatusSnapshot  # noqa: E402
from status.service import StatusService  # noqa: E402
from storage.sqlite import Database  # noqa: E402


def main(
    argv: Sequence[str] | None = None,
    *,
    database_path: Path | None = None,
    output_dir: Path | None = None,
) -> int:
    """Run a command and return the documented process exit code."""
    arguments = list(argv) if argv is not None else list(sys.argv[1:])
    if arguments == ["--version"]:
        print(__version__)
        return 0
    if arguments != ["--version"] and argv is None:
        compatibility = check_runtime()
        if not compatibility.supported:
            print(compatibility.message, file=sys.stderr)
            return 2
    try:
        args = _parser().parse_args(arguments)
    except SystemExit:
        return 2
    if database_path is not None and args.command in {"status", "export"}:
        return _legacy_local(args.command, database_path, output_dir or Path("output"))
    try:
        config = ApplicationConfigLoader().load(Path(args.config))
        config = replace(
            config,
            database_path=Path(args.database).resolve() if args.database else config.database_path,
            input_path=Path(args.input).resolve() if args.input else config.input_path,
            output_path=Path(args.output).resolve() if args.output else config.output_path,
            log_level=args.log_level or config.log_level,
        )
        if args.command == "validate":
            outcome = CollectionService(
                config, ApplicationFactory(config), ShutdownController()
            ).validate()
            print(f"検証完了: {len(outcome.planned_queries)} conditions")
            print(_playwright_status(config.playwright_enabled))
            return outcome.exit_code
        factory = ApplicationFactory(config)
        if args.command == "live-check":
            live = LiveValidationConfig.load(config.config_file.parent / "live_validation.yaml")
            service = LiveValidationService(config, live)
            for line in service.preview():
                print(line)
            return service.run(yes=args.yes).exit_code
        if args.command == "review-import":
            database = Database(config.database_path)
            database.initialize()
            review_path = Path(args.file)
            if not review_path.is_absolute():
                review_path = config.project_root / review_path
            count = ManualReviewService(database).import_csv(review_path, args.reviewer)
            report = ManualReviewService(database).accuracy()
            print(f"レビュー取込: {count}件 / 統計十分性: {report.statistically_sufficient}")
            return 0
        if args.command == "live-report":
            database = Database(config.database_path)
            database.initialize()
            LiveReportService(database).export(
                config.output_path / "live_validation_report.xlsx",
                config.input_path / "live_review.csv",
            )
            print("実通信検証レポートを生成しました。")
            return 0
        if args.command in {"collect", "resume"}:
            factory.shutdown.install()
            outcome = CollectionService(config, factory, factory.shutdown).run(
                args.command, dry_run=args.dry_run
            )
            if args.dry_run:
                print("\n".join(outcome.planned_queries))
            return outcome.exit_code
        components = factory.build()
        if args.command == "status":
            print(_format_status(components.status_service.get_status()))
            print(_playwright_status(config.playwright_enabled))
        elif args.command == "export":
            result = components.export_service.export_all()
            print(f"出力完了: {len(result.files)} files")
        elif not args.yes:
            print("reset-retries requires --yes", file=sys.stderr)
            return 2
        else:
            print(f"再試行解除: {components.progress.reset_retries()}")
        return 0
    except (ApplicationConfigError, InputValidationError, ValueError) as exc:
        print(f"入力エラー: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"内部エラー: {exc}", file=sys.stderr)
        return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m src.cli")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "command",
        choices=(
            "collect", "resume", "status", "export", "validate", "reset-retries",
            "live-check", "review-import", "live-report",
        ),
    )
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument("--database")
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--log-level", choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--file", default="input/live_review.csv")
    parser.add_argument("--reviewer")
    return parser


def _legacy_local(command: str, database: Path, output: Path) -> int:
    """Preserve the injectable Phase 8 status/export API used by callers."""
    try:
        if command == "status":
            print(_format_status(StatusService(Database(database)).get_status()))
        else:
            result = ExportService(Database(database), output).export_all()
            print(f"出力完了: {len(result.files)} files")
        return 0
    except Exception as exc:
        print(f"内部エラー: {exc}", file=sys.stderr)
        return 1


def _playwright_status(enabled: bool) -> str:
    """Describe configured browser fallback without starting a browser."""
    if not enabled:
        return "Playwright fallback: 無効 (requestsのみ)"
    try:
        available = importlib.util.find_spec("playwright") is not None
    except ValueError:
        available = False
    return f"Playwright fallback: 有効 / {'利用可能' if available else '利用不可'}"


def _format_status(status: StatusSnapshot) -> str:
    """Format status only at the presentation boundary."""
    values = (
        ("検索条件数", status.search_condition_count),
        ("完了条件数", status.completed_condition_count),
        ("未処理条件数", status.pending_condition_count),
        ("処理中条件数", status.processing_condition_count),
        ("営業対象件数", status.business_target_count),
        ("公式サイト件数", status.official_count),
        ("携帯番号件数", status.mobile_count),
        ("電話番号なし件数", status.no_phone_count),
        ("要確認件数", status.review_required_count),
        ("除外件数", status.excluded_count),
        ("再試行待ち件数", status.retry_waiting_count),
        ("エラー件数", status.error_count),
        ("本日の処理件数", status.today_processed_count),
        ("累計処理件数", status.total_processed_count),
        ("現在処理中のURL", ", ".join(status.current_urls) or "なし"),
        ("次回再試行時刻", status.next_retry_at or "なし"),
    )
    return "\n".join(f"{label}: {value}" for label, value in values)


if __name__ == "__main__":
    raise SystemExit(main())
