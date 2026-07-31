"""Testable model of the Windows Python 3.13 candidate selection policy."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PythonCandidate:
    """One executable candidate in deterministic discovery order."""

    executable: str
    prefix: tuple[str, ...]
    source: str


@dataclass(frozen=True, slots=True)
class PythonProbe:
    """Safe metadata returned by invoking a candidate with a short Python command."""

    executable: str
    version: tuple[int, int]
    bits: int
    exists: bool = True


def candidates(
    environment: Mapping[str, str],
    get_command: str | None,
    where_results: Iterable[str],
    root: Path,
) -> tuple[PythonCandidate, ...]:
    """Return candidates in the exact Phase 11.2.2.1 priority order."""
    values: list[PythonCandidate] = []
    _add(values, environment.get("HPCC_PYTHON"), (), "HPCC_PYTHON")
    _add(values, get_command, (), "Get-Command python.exe")
    for value in where_results:
        _add(values, value, (), "where.exe python")
    _add_location(values, environment.get("pythonLocation"), "pythonLocation")
    _add_location(values, environment.get("Python_ROOT_DIR"), "Python_ROOT_DIR")
    _add(values, str(root / ".venv" / "Scripts" / "python.exe"), (), ".venv")
    _add(values, "py", ("-3.13",), "py -3.13")
    _add(values, "python", (), "python")
    _add(values, "python3", (), "python3")
    return tuple(values)


def select_python(
    values: Iterable[PythonCandidate],
    probe: Callable[[PythonCandidate], PythonProbe | None],
) -> tuple[PythonCandidate, PythonProbe] | None:
    """Select the first real, non-Store, 64bit Python 3.13 candidate."""
    for candidate in values:
        if is_store_alias(candidate.executable):
            continue
        result = probe(candidate)
        if result is None or not result.exists or is_store_alias(result.executable):
            continue
        if result.version == (3, 13) and result.bits == 64:
            return candidate, result
    return None


def is_store_alias(value: str) -> bool:
    """Reject Microsoft Store execution aliases instead of launching the Store."""
    return "\\windowsapps\\" in value.replace("/", "\\").lower()


def _add(
    values: list[PythonCandidate],
    executable: str | None,
    prefix: tuple[str, ...],
    source: str,
) -> None:
    if not executable:
        return
    candidate = PythonCandidate(executable.strip().strip('"'), prefix, source)
    if (candidate.executable, candidate.prefix) not in {
        (item.executable, item.prefix) for item in values
    }:
        values.append(candidate)


def _add_location(
    values: list[PythonCandidate], location: str | None, source: str
) -> None:
    if location:
        _add(values, str(Path(location) / "python.exe"), (), source)
