"""Ordered provider fallback, scoring, and cross-provider URL de-duplication."""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol
from urllib.parse import SplitResult, urlsplit, urlunsplit

from search.audit import ProviderAuditRecord
from search.providers.base import SearchProvider, SearchProviderError, SearchResult


class ProviderAuditor(Protocol):
    """Persistence boundary used by the search chain."""

    def save(self, record: ProviderAuditRecord) -> None:
        """Persist one provider execution."""


class ProviderChain:
    """Merge providers by configured priority, rank, and query-term evidence."""

    def __init__(
        self,
        providers: list[SearchProvider],
        priorities: dict[str, int] | None = None,
        logger: logging.Logger | None = None,
        auditor: ProviderAuditor | None = None,
        configured: dict[str, bool] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("at least one search provider is required")
        names = [provider.name for provider in providers]
        if len(names) != len(set(names)):
            raise ValueError("provider names must be unique")
        self._providers = tuple(providers)
        self._priorities = priorities or {
            provider.name: index * 10 for index, provider in enumerate(providers, 1)
        }
        self._logger = logger or logging.getLogger(__name__)
        self._auditor = auditor
        self._run_id = "unassigned"
        self._stopped: dict[str, str] = {}
        self._configured = configured or {provider.name: True for provider in providers}

    def set_run_id(self, run_id: str) -> None:
        """Attach the application run identifier before the first query executes."""
        self._run_id = run_id

    def search(self, query: str, limit: int) -> list[SearchResult]:
        """Run every available provider and retain the strongest normalized URL."""
        if not query.strip():
            raise ValueError("query must not be empty")
        if limit < 1:
            raise ValueError("limit must be positive")
        selected: dict[str, SearchResult] = {}
        self._audit_disabled(query)
        for provider in self._providers:
            started = datetime.now(UTC)
            timer = perf_counter()
            stopped_reason = self._stopped.get(provider.name)
            if stopped_reason:
                self._audit(
                    provider, query, started, timer, 0, 0, 0, "provider_stopped",
                    stopped_reason, None, None,
                )
                continue
            try:
                results = provider.search(query, limit)
            except SearchProviderError as exc:
                self._logger.warning("search provider %s failed: %s", provider.name, exc)
                metadata = provider.response_metadata
                self._audit(
                    provider,
                    query,
                    started,
                    timer,
                    0,
                    0,
                    0,
                    exc.failure_type,
                    str(exc),
                    exc.http_status if exc.http_status is not None else metadata.http_status,
                    exc.final_url or metadata.final_url,
                )
                if exc.failure_type in {"http_403", "http_429", "captcha", "block"}:
                    self._stopped[provider.name] = str(exc)
                continue
            except Exception as exc:
                self._logger.exception("unexpected search provider failure: %s", provider.name)
                self._audit(
                    provider, query, started, timer, 0, 0, 0,
                    "unexpected_error", str(exc) or type(exc).__name__, None, None,
                )
                continue
            accepted = 0
            duplicates = 0
            for result in results:
                normalized = normalize_search_url(result.url)
                if not normalized:
                    continue
                scored = self._score(query, result)
                current = selected.get(normalized)
                if current is None or scored.chain_score > current.chain_score:
                    selected[normalized] = scored
                if current is None:
                    accepted += 1
                else:
                    duplicates += 1
            metadata = provider.response_metadata
            failure_type = "empty_results" if not results else None
            self._audit(
                provider, query, started, timer, len(results), accepted, duplicates,
                failure_type, "HTTP 200 but no search results" if failure_type else None,
                metadata.http_status, metadata.final_url,
            )
        ordered = sorted(
            selected.values(),
            key=lambda item: (-item.chain_score, item.provider, item.rank, item.url),
        )
        return ordered[:limit]

    def _audit_disabled(self, query: str) -> None:
        if self._auditor is None:
            return
        active = {provider.name for provider in self._providers}
        now = datetime.now(UTC).isoformat()
        for name, enabled in self._configured.items():
            if enabled or name in active:
                continue
            self._auditor.save(
                ProviderAuditRecord(
                    self._run_id, query, name, False, now, now, None, 0, 0, 0,
                    "disabled", "disabled by config/providers.yaml", None, 0,
                )
            )

    def _audit(
        self,
        provider: SearchProvider,
        query: str,
        started: datetime,
        timer: float,
        results: int,
        accepted: int,
        duplicates: int,
        failure_type: str | None,
        failure_message: str | None,
        http_status: int | None,
        final_url: str | None,
    ) -> None:
        if self._auditor is None:
            return
        finished = datetime.now(UTC)
        self._auditor.save(
            ProviderAuditRecord(
                self._run_id, query, provider.name, True, started.isoformat(),
                finished.isoformat(), http_status, results, accepted, duplicates,
                failure_type, failure_message, final_url,
                max(0, round((perf_counter() - timer) * 1000)),
            )
        )

    def _score(self, query: str, result: SearchResult) -> SearchResult:
        match = query_match_rate(query, result)
        priority = self._priorities.get(result.provider, 999)
        provider_points = max(0.0, 100.0 - float(priority))
        rank_points = max(0.0, 21.0 - float(result.rank))
        total = match * 100.0 + provider_points * 0.3 + rank_points
        return replace(result, match_score=round(match, 4), chain_score=round(total, 4))


def query_match_rate(query: str, result: SearchResult) -> float:
    """Return the fraction of meaningful query terms present in result evidence."""
    terms = tuple(
        dict.fromkeys(
            term.lower()
            for term in re.findall(r"[^\s\"]+", query)
            if term and not term.startswith("site:") and term != "公式"
        )
    )
    if not terms:
        return 0.0
    evidence = " ".join((result.title, result.snippet, result.url)).lower()
    return sum(term in evidence for term in terms) / len(terms)


def normalize_search_url(url: str) -> str:
    """Normalize HTTP(S) URLs for de-duplication across providers."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    scheme = parts.scheme.lower()
    hostname = parts.hostname.lower()
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = hostname if port is None or default_port else f"{hostname}:{port}"
    return urlunsplit(SplitResult(scheme, netloc, parts.path.rstrip("/") or "/", parts.query, ""))
