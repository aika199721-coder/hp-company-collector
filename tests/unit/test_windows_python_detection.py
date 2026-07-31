"""Offline regressions for Windows Python discovery and selection priority."""

from pathlib import Path

import pytest

from scripts.windows.python_detection import (
    PythonCandidate,
    PythonProbe,
    candidates,
    is_store_alias,
    select_python,
)


def _candidate_order(environment: dict[str, str] | None = None) -> tuple[str, ...]:
    return tuple(
        item.source
        for item in candidates(
            environment or {},
            r"C:\GetCommand\python.exe",
            (r"C:\Where\python.exe",),
            Path(r"C:\Project"),
        )
    )


def test_candidate_priority_starts_with_environment_command_and_where() -> None:
    order = _candidate_order(
        {
            "HPCC_PYTHON": r"C:\Actions\python.exe",
            "pythonLocation": r"C:\Toolcache",
            "Python_ROOT_DIR": r"C:\Root",
        }
    )

    assert order == (
        "HPCC_PYTHON",
        "Get-Command python.exe",
        "where.exe python",
        "pythonLocation",
        "Python_ROOT_DIR",
        ".venv",
        "py -3.13",
        "python",
        "python3",
    )


@pytest.mark.parametrize(
    ("version", "bits", "accepted"),
    [((3, 13), 64, True), ((3, 13), 32, False), ((3, 12), 64, False)],
)
def test_version_and_bitness_are_required(
    version: tuple[int, int], bits: int, accepted: bool
) -> None:
    value = PythonCandidate("python.exe", (), "python")
    selected = select_python(
        (value,), lambda _: PythonProbe("C:\\Python\\python.exe", version, bits)
    )

    assert (selected is not None) is accepted


def test_store_alias_and_missing_executable_are_rejected() -> None:
    store = PythonCandidate(
        r"C:\Users\u\AppData\Local\Microsoft\WindowsApps\python.exe", (), "where"
    )
    missing = PythonCandidate(r"C:\missing\python.exe", (), "HPCC_PYTHON")

    assert is_store_alias(store.executable)
    assert select_python((store, missing), lambda _: PythonProbe("", (3, 13), 64, False)) is None


def test_first_valid_candidate_wins_when_multiple_are_available() -> None:
    values = (
        PythonCandidate("hpcc.exe", (), "HPCC_PYTHON"),
        PythonCandidate("command.exe", (), "Get-Command python.exe"),
        PythonCandidate("py", ("-3.13",), "py -3.13"),
    )
    probes = {
        "hpcc.exe": PythonProbe("hpcc.exe", (3, 12), 64),
        "command.exe": PythonProbe("command.exe", (3, 13), 64),
        "py": PythonProbe("py.exe", (3, 13), 64),
    }

    selected = select_python(values, lambda item: probes[item.executable])

    assert selected is not None
    assert selected[0].source == "Get-Command python.exe"


def test_valid_hpcc_python_has_absolute_priority() -> None:
    values = (
        PythonCandidate("actions.exe", (), "HPCC_PYTHON"),
        PythonCandidate("command.exe", (), "Get-Command python.exe"),
    )

    selected = select_python(
        values, lambda item: PythonProbe(item.executable, (3, 13), 64)
    )

    assert selected is not None
    assert selected[0].source == "HPCC_PYTHON"
