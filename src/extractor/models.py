"""Typed values shared by extraction components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExtractedValue:
    """A normalized string and the extraction source that won priority."""

    value: str
    source: str


@dataclass(frozen=True, slots=True)
class ExtractedAddress:
    """Normalized Japanese address components and provenance."""

    address: str
    postal_code: str | None
    prefecture: str | None
    municipality: str | None
    source: str


@dataclass(frozen=True, slots=True)
class ExtractedPhone:
    """Normalized non-FAX phone number with classification and estimated use."""

    number: str
    kind: str
    usage: str
    source: str
