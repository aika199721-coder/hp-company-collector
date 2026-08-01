"""Confirmation gate tests that never access an external site."""

from pathlib import Path

from application.config import ApplicationConfigLoader
from live.config import LiveValidationConfig
from live.service import LiveValidationService, _has_required_results
from tests.unit.test_application_config import copy_config

ROOT = Path(__file__).resolve().parents[2]


def _service(tmp_path: Path, answer: str = "N", interactive: bool = True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    default = copy_config(tmp_path)
    (default.parent / "live_validation.yaml").write_bytes(
        (ROOT / "config/live_validation.yaml").read_bytes()
    )
    config = ApplicationConfigLoader({}).load(default)
    config.input_path.mkdir()
    (config.input_path / "search_conditions.csv").write_text(
        "都道府県,市区町村,検索業種,最大取得件数,有効\n",
        encoding="utf-8-sig",
    )
    live = LiveValidationConfig.load(default.parent / "live_validation.yaml")
    return LiveValidationService(
        config, live, input_func=lambda _: answer, interactive=lambda: interactive
    ), config


def test_decline_and_noninteractive_without_yes_never_start(tmp_path: Path) -> None:
    service, config = _service(tmp_path, "N")
    assert service.run().started is False
    assert not config.database_path.exists()

    service, config = _service(tmp_path / "second", interactive=False)
    assert service.run().exit_code == 2
    assert not config.database_path.exists()


def test_explicit_yes_can_start_bounded_empty_run(tmp_path: Path) -> None:
    service, config = _service(tmp_path, interactive=False)

    outcome = service.run(yes=True)

    assert outcome.started is True
    assert outcome.exit_code != 0
    assert config.database_path.exists()
    assert (config.output_path / "live_validation_report.xlsx").exists()


def test_live_success_requires_official_fetch_and_contact() -> None:
    """A completed collection without all three outcomes is not successful."""
    from types import SimpleNamespace

    complete = SimpleNamespace(
        official_count=1,
        results=(
            SimpleNamespace(
                fetch_result=SimpleNamespace(status_code=200),
                extraction_result=SimpleNamespace(phones=("098",), address=None),
            ),
        ),
    )
    missing_contact = SimpleNamespace(
        official_count=1,
        results=(
            SimpleNamespace(
                fetch_result=SimpleNamespace(status_code=200),
                extraction_result=SimpleNamespace(phones=(), address=None),
            ),
        ),
    )

    assert _has_required_results((complete,)) is True
    assert _has_required_results((missing_contact,)) is False
