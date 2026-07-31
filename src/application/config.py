"""Validated integration of all operator-editable application configuration."""

from __future__ import annotations

import os
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from pipeline.models import PipelineLimits

_REQUIRED_FILES = (
    "default.yaml",
    "providers.yaml",
    "pipeline.yaml",
    "scoring.yaml",
    "industry_keywords.yaml",
    "exclude_domains.txt",
)
_KNOWN_DEFAULT_KEYS = {"project", "paths", "search", "crawler", "logging", "runtime"}


class ApplicationConfigError(ValueError):
    """User-correctable configuration error."""


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Condition failure, export, and input-validation behavior."""

    input_mode: str
    continue_on_condition_error: bool
    export_after_each_condition: bool
    export_on_shutdown: bool


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    """Fully validated configuration with project-root-resolved paths."""

    project_root: Path
    config_file: Path
    database_path: Path
    input_path: Path
    output_path: Path
    log_path: Path
    log_level: str
    user_agent: str
    request_timeout_seconds: float
    per_domain_delay_seconds: float
    max_redirects: int
    playwright_enabled: bool
    providers: dict[str, dict[str, Any]]
    pipeline_limits: PipelineLimits
    scoring: dict[str, Any]
    industries: dict[str, Any]
    excluded_domains: tuple[str, ...]
    runtime: RuntimeConfig
    warnings: tuple[str, ...]


class ApplicationConfigLoader:
    """Load, combine, validate, and partially override all project config files."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = dict(environ if environ is not None else os.environ)

    def load(self, default_file: Path) -> ApplicationConfig:
        """Load the config set or raise one user-facing configuration error."""
        default_file = Path(default_file).resolve()
        config_dir = default_file.parent
        for name in _REQUIRED_FILES:
            path = config_dir / name
            if not path.is_file():
                raise ApplicationConfigError(f"Required configuration file is missing: {path}")
        default = _read_yaml(default_file)
        local_file = config_dir / "local.yaml"
        if local_file.is_file():
            default = _merge(default, _read_yaml(local_file))
        providers_doc = _read_yaml(config_dir / "providers.yaml")
        pipeline_doc = _read_yaml(config_dir / "pipeline.yaml")
        scoring = _read_yaml(config_dir / "scoring.yaml")
        industries_doc = _read_yaml(config_dir / "industry_keywords.yaml")
        project_root = config_dir.parent
        warning_messages = tuple(
            f"Unknown top-level setting: {key}"
            for key in default
            if key not in _KNOWN_DEFAULT_KEYS
        )
        for message in warning_messages:
            warnings.warn(message, UserWarning, stacklevel=2)

        paths = _mapping(default, "paths")
        crawler = _mapping(default, "crawler")
        logging = _mapping(default, "logging")
        runtime_doc = _mapping(default, "runtime")
        providers = _mapping(providers_doc, "providers")
        industries = _mapping(industries_doc, "industries")
        _validate_providers(providers)
        _validate_scoring(scoring)
        runtime = RuntimeConfig(
            input_mode=_choice(runtime_doc, "input_mode", {"strict", "lenient"}),
            continue_on_condition_error=_boolean(runtime_doc, "continue_on_condition_error"),
            export_after_each_condition=_boolean(runtime_doc, "export_after_each_condition"),
            export_on_shutdown=_boolean(runtime_doc, "export_on_shutdown"),
        )
        database = self._environ.get("HPCC_DATABASE", str(paths["database"]))
        input_value = self._environ.get("HPCC_INPUT", str(paths["input"]))
        output = self._environ.get("HPCC_OUTPUT", str(paths["output"]))
        log_value = self._environ.get("HPCC_LOG_FILE", str(logging["file"]))
        level = self._environ.get("HPCC_LOG_LEVEL", str(logging["level"])).upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ApplicationConfigError(f"Invalid log level: {level}")
        try:
            timeout = float(crawler["request_timeout_seconds"])
            delay = float(crawler["per_domain_delay_seconds"])
            redirects = int(crawler["max_redirects"])
            user_agent = str(crawler["user_agent"]).strip()
            playwright = _mapping(crawler, "playwright")
            playwright_enabled = _boolean(playwright, "enabled")
        except (KeyError, TypeError, ValueError) as exc:
            raise ApplicationConfigError("Crawler settings are incomplete") from exc
        if timeout <= 0 or delay <= 0 or redirects < 0 or not user_agent:
            raise ApplicationConfigError("Crawler settings contain invalid values")
        excluded = _read_domains(config_dir / "exclude_domains.txt")
        return ApplicationConfig(
            project_root,
            default_file,
            _resolve(project_root, database),
            _resolve(project_root, input_value),
            _resolve(project_root, output),
            _resolve(project_root, log_value),
            level,
            user_agent,
            timeout,
            delay,
            redirects,
            playwright_enabled,
            {str(key): dict(value) for key, value in providers.items()},
            PipelineLimits.from_config(pipeline_doc),
            scoring,
            industries,
            excluded,
            runtime,
            warning_messages,
        )


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ApplicationConfigError(f"Unable to read YAML: {path}") from exc
    if not isinstance(value, dict):
        raise ApplicationConfigError(f"YAML root must be a mapping: {path}")
    return value


def _merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge an optional local configuration without mutating inputs."""
    merged = dict(base)
    for key, value in override.items():
        current = merged.get(key)
        merged[key] = (
            _merge(current, value)
            if isinstance(current, Mapping) and isinstance(value, Mapping)
            else value
        )
    return merged


def _mapping(value: Mapping[str, Any], key: str) -> dict[str, Any]:
    result = value.get(key)
    if not isinstance(result, dict):
        raise ApplicationConfigError(f"Required mapping is missing: {key}")
    return result


def _validate_providers(providers: Mapping[str, Any]) -> None:
    if not providers:
        raise ApplicationConfigError("At least one search provider is required")
    for name, settings in providers.items():
        if not isinstance(settings, dict):
            raise ApplicationConfigError(f"Provider settings must be a mapping: {name}")
        if not isinstance(settings.get("enabled"), bool):
            raise ApplicationConfigError(f"Provider enabled must be boolean: {name}")
        priority = settings.get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool):
            raise ApplicationConfigError(f"Provider priority must be integer: {name}")


def _validate_scoring(scoring: Mapping[str, Any]) -> None:
    thresholds = _mapping(scoring, "thresholds")
    for key in ("official", "business_target", "review_margin"):
        if not isinstance(thresholds.get(key), int):
            raise ApplicationConfigError(f"Scoring threshold must be integer: {key}")


def _boolean(value: Mapping[str, Any], key: str) -> bool:
    result = value.get(key)
    if not isinstance(result, bool):
        raise ApplicationConfigError(f"Setting must be boolean: {key}")
    return result


def _choice(value: Mapping[str, Any], key: str, choices: set[str]) -> str:
    result = str(value.get(key, ""))
    if result not in choices:
        raise ApplicationConfigError(f"Invalid {key}: {result}")
    return result


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _read_domains(path: Path) -> tuple[str, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ApplicationConfigError(f"Unable to read excluded domains: {path}") from exc
    return tuple(
        line.strip().lower().rstrip(".")
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    )
