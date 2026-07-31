"""Strict configuration for deliberately small live validation runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class LiveValidationConfig:
    """Hard safety ceilings for a manually confirmed live run."""

    require_confirmation: bool
    max_conditions: int
    max_business_targets: int
    max_candidates: int
    max_http_requests: int
    max_requests_per_domain: int
    max_runtime_seconds: int
    timeout_seconds: float
    delay_seconds: float
    max_redirects: int
    max_response_bytes: int
    consecutive_403_limit: int
    max_queries: int
    max_results_per_query: int
    stop_on_robots_error: bool
    stop_on_rate_limit: bool
    stop_on_captcha_signal: bool
    stop_on_block_page_signal: bool

    @classmethod
    def load(cls, path: Path) -> LiveValidationConfig:
        """Load a separated live configuration and reject unsafe values."""
        try:
            document = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
            runtime = _mapping(document, "runtime")
            crawler = _mapping(document, "crawler")
            search = _mapping(document, "search")
            safety = _mapping(document, "safety")
            playwright = _mapping(crawler, "playwright")
            if not _boolean(runtime, "live_validation"):
                raise ValueError("live_validation must be true")
            if _boolean(playwright, "enabled"):
                raise ValueError("Playwright must remain disabled for initial validation")
            result = cls(
                _boolean(runtime, "require_confirmation"),
                _integer(runtime, "max_conditions"),
                _integer(runtime, "max_business_targets"),
                _integer(runtime, "max_candidates"),
                _integer(runtime, "max_http_requests"),
                _integer(runtime, "max_requests_per_domain"),
                _integer(runtime, "max_runtime_seconds"),
                float(crawler["request_timeout_seconds"]),
                float(crawler["default_delay_seconds"]),
                _integer(crawler, "max_redirects"),
                _integer(crawler, "max_response_bytes"),
                _integer(crawler, "consecutive_403_limit"),
                _integer(search, "max_queries"),
                _integer(search, "max_results_per_query"),
                _boolean(safety, "stop_on_robots_error"),
                _boolean(safety, "stop_on_rate_limit"),
                _boolean(safety, "stop_on_captcha_signal"),
                _boolean(safety, "stop_on_block_page_signal"),
            )
        except (KeyError, OSError, TypeError, yaml.YAMLError) as exc:
            raise ValueError(f"Invalid live validation configuration: {path}") from exc
        if result.max_conditions != 1 or result.max_business_targets > 3:
            raise ValueError(
                "Initial live validation is limited to one condition and three targets"
            )
        if result.max_candidates > 20 or result.delay_seconds < 5:
            raise ValueError("Live candidate ceiling is 20 and delay must be at least five seconds")
        return result


def _mapping(value: Any, key: str) -> dict[str, Any]:
    result = value.get(key) if isinstance(value, dict) else None
    if not isinstance(result, dict):
        raise ValueError(f"Missing live validation mapping: {key}")
    return result


def _integer(value: dict[str, Any], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool) or result < 1:
        raise ValueError(f"Live validation integer must be positive: {key}")
    return result


def _boolean(value: dict[str, Any], key: str) -> bool:
    result = value.get(key)
    if not isinstance(result, bool):
        raise ValueError(f"Live validation setting must be boolean: {key}")
    return result
