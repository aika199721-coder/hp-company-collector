"""Offline application workflow and run-history integration tests."""

from pathlib import Path

from application.collection import CollectionService
from application.config import ApplicationConfigLoader
from application.factory import ApplicationFactory
from pipeline.models import PipelineSummary
from tests.unit.test_application_config import copy_config


class FakeCoordinator:
    """Return summaries without search or HTTP."""

    def __init__(self, fail_on: str = "") -> None:
        self.calls: list[str] = []
        self.fail_on = fail_on

    def run(self, condition: object) -> PipelineSummary:
        industry = condition.industry
        self.calls.append(industry)
        if industry == self.fail_on:
            raise RuntimeError("condition failed")
        return PipelineSummary(1, 1, 1, 1, 0, 0, 0, 0, 0, {}, ())


class FakeExport:
    """Count export invocations without writing files."""

    def __init__(self) -> None:
        self.calls = 0

    def export_all(self) -> None:
        self.calls += 1


def _input(path: Path) -> None:
    path.mkdir()
    (path / "search_conditions.csv").write_text(
        "都道府県,市区町村,検索業種,最大取得件数,有効\n"
        "東京都,千代田区,建設業,1,はい\n"
        "大阪府,大阪市,美容室,1,はい\n"
        "京都府,京都市,無効業種,1,いいえ\n",
        encoding="utf-8-sig",
    )


def test_collect_continues_after_condition_error_and_records_run(tmp_path: Path) -> None:
    config = ApplicationConfigLoader({}).load(copy_config(tmp_path))
    _input(config.input_path)
    coordinator = FakeCoordinator("建設業")
    exporter = FakeExport()
    factory = ApplicationFactory(
        config,
        overrides={"coordinator": coordinator, "export_service": exporter},
    )

    result = CollectionService(config, factory, factory.shutdown).run("collect")

    assert result.exit_code == 3
    assert coordinator.calls == ["建設業", "美容室"]
    assert exporter.calls == 1
    with factory.build().database.connect() as connection:
        run = connection.execute("SELECT * FROM runs WHERE run_id = ?", (result.run_id,)).fetchone()
    assert run["status"] == "partial"
    assert run["conditions_completed"] == 1


def test_dry_run_does_not_create_database_or_call_coordinator(tmp_path: Path) -> None:
    config = ApplicationConfigLoader({}).load(copy_config(tmp_path))
    _input(config.input_path)
    coordinator = FakeCoordinator()
    factory = ApplicationFactory(config, overrides={"coordinator": coordinator})

    result = CollectionService(config, factory, factory.shutdown).run("collect", dry_run=True)

    assert result.exit_code == 0
    assert len(result.planned_queries) == 2
    assert coordinator.calls == []
    assert not config.database_path.exists()
