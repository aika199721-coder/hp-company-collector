"""Configuration manager tests."""

from pathlib import Path

import pytest

from utils.config import ConfigManager, ConfigurationError

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def test_loads_default_and_supporting_configuration() -> None:
    manager = ConfigManager(CONFIG_DIR)

    config = manager.load()

    assert config["crawler"]["respect_robots_txt"] is True
    assert [name for name, _ in manager.load_providers()] == [
        "bing_rss",
        "duckduckgo_html",
        "mojeek",
    ]
    assert manager.load_industries()["restaurant"]["display_name"] == "飲食店"
    assert "wikipedia.org" in manager.load_excluded_domains()


def test_override_is_recursive_and_cannot_disable_robots(tmp_path: Path) -> None:
    override = tmp_path / "override.yaml"
    override.write_text("crawler:\n  request_timeout_seconds: 7\n", encoding="utf-8")
    config = ConfigManager(CONFIG_DIR).load(override)
    assert config["crawler"]["request_timeout_seconds"] == 7
    assert config["crawler"]["per_domain_delay_seconds"] == 2.0

    override.write_text("crawler:\n  respect_robots_txt: false\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="must remain enabled"):
        ConfigManager(CONFIG_DIR).load(override)


def test_invalid_provider_configuration_has_context(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text(
        "providers:\n  broken:\n    enabled: yes\n", encoding="utf-8"
    )

    with pytest.raises(ConfigurationError, match="broken priority"):
        ConfigManager(config_dir).load_providers()
