"""Display-only status model for CLI and future user interfaces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StatusSnapshot:
    """Current and cumulative SQLite pipeline counters."""

    search_condition_count: int
    completed_condition_count: int
    pending_condition_count: int
    processing_condition_count: int
    business_target_count: int
    official_count: int
    mobile_count: int
    no_phone_count: int
    review_required_count: int
    excluded_count: int
    retry_waiting_count: int
    error_count: int
    today_processed_count: int
    total_processed_count: int
    current_urls: tuple[str, ...]
    next_retry_at: str | None
