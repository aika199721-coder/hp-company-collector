"""Phase 9 Step 1 ApplicationConfig tests."""

from pathlib import Path

import pytest

from application.config import ApplicationConfigError, ApplicationConfigLoader

ROOT = Path(__file__).resolve().parents[2]


def copy_config(tmp_path: Path) -> Path:
    """Copy required repository config files into a temporary project."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    for name in (
        "default.yaml",
        "providers.yaml",
        "pipeline.yaml",
        "scoring.yaml",
        "industry_keywords.yaml",
        "exclude_domains.txt",
    ):
        (config_dir / name).write_bytes((ROOT / "config" / name).read_bytes())
    return config_dir / "default.yaml"


def test_loads_all_files_resolves_paths_and_environment(tmp_path: Path) -> None:
    default = copy_config(tmp_path)
    env = {"HPCC_DATABASE": "custom/app.sqlite3", "HPCC_LOG_LEVEL": "DEBUG"}

    config = ApplicationConfigLoader(env).load(default)

    assert config.database_path == tmp_path / "custom/app.sqlite3"
    assert config.input_path == tmp_path / "input"
    assert config.providers["bing_rss"]["enabled"] is True
    assert config.providers["brave_search"]["enabled"] is False
    assert config.pipeline_limits.max_candidates_per_condition == 2000
    assert config.log_level == "DEBUG"
    assert "itp.ne.jp" in config.excluded_domains


def test_missing_required_file_is_user_configuration_error(tmp_path: Path) -> None:
    default = copy_config(tmp_path)
    (default.parent / "scoring.yaml").unlink()

    with pytest.raises(ApplicationConfigError, match=r"scoring\.yaml"):
        ApplicationConfigLoader({}).load(default)


def test_optional_local_config_overrides_defaults(tmp_path: Path) -> None:
    default = copy_config(tmp_path)
    (default.parent / "local.yaml").write_text(
        "logging:\n  level: WARNING\n",
        encoding="utf-8",
    )

    config = ApplicationConfigLoader({}).load(default)

    assert config.log_level == "WARNING"
