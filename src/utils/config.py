"""YAML based configuration loading and validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ConfigurationError(ValueError):
    """Raised when application configuration is missing or unsafe."""


class ConfigManager:
    """Load defaults and optional overrides without mutating source mappings."""

    def __init__(self, config_dir: Path) -> None:
        self.config_dir = Path(config_dir)

    def load(self, override_file: Path | None = None) -> dict[str, Any]:
        """Return validated defaults, recursively merged with an optional override."""
        config = self._read_yaml(self.config_dir / "default.yaml")
        if override_file is not None:
            config = _deep_merge(config, self._read_yaml(Path(override_file)))
        self._validate(config)
        return config

    def load_industries(self) -> dict[str, Any]:
        """Return the configured industry keyword mapping."""
        content = self._read_yaml(self.config_dir / "industry_keywords.yaml")
        industries = content.get("industries")
        if not isinstance(industries, dict) or not industries:
            raise ConfigurationError("industries must be a non-empty mapping")
        return industries

    def load_providers(self) -> list[tuple[str, dict[str, Any]]]:
        """Return enabled providers sorted by numeric priority."""
        content = self._read_yaml(self.config_dir / "providers.yaml")
        providers = content.get("providers")
        if not isinstance(providers, dict):
            raise ConfigurationError("providers must be a mapping")
        for name, settings in providers.items():
            if not isinstance(settings, dict):
                raise ConfigurationError(f"provider {name} settings must be a mapping")
            enabled = settings.get("enabled")
            priority = settings.get("priority")
            if not isinstance(enabled, bool):
                raise ConfigurationError(f"provider {name} enabled must be boolean")
            if not isinstance(priority, int) or isinstance(priority, bool):
                raise ConfigurationError(f"provider {name} priority must be an integer")
        enabled = [(name, settings) for name, settings in providers.items() if settings["enabled"]]
        return sorted(enabled, key=lambda item: item[1]["priority"])

    def load_excluded_domains(self) -> frozenset[str]:
        """Return normalized domains, ignoring empty and comment lines."""
        path = self.config_dir / "exclude_domains.txt"
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ConfigurationError(f"Unable to read configuration: {path}") from exc
        return frozenset(
            line.strip().lower().rstrip(".")
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        )

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError(f"Unable to read configuration: {path}") from exc
        if not isinstance(value, dict):
            raise ConfigurationError(f"Configuration root must be a mapping: {path}")
        return value

    @staticmethod
    def _validate(config: dict[str, Any]) -> None:
        try:
            crawler = config["crawler"]
            delay = crawler["per_domain_delay_seconds"]
            timeout = crawler["request_timeout_seconds"]
        except (KeyError, TypeError) as exc:
            raise ConfigurationError("crawler settings are incomplete") from exc
        if crawler.get("respect_robots_txt") is not True:
            raise ConfigurationError("respect_robots_txt must remain enabled")
        if not isinstance(delay, (int, float)) or isinstance(delay, bool) or delay <= 0:
            raise ConfigurationError("per_domain_delay_seconds must be positive")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise ConfigurationError("request_timeout_seconds must be positive")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge mappings and replace scalar/list values."""
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result
