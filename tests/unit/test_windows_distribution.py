"""Offline static guarantees for thin Windows launchers."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = (
    "setup", "validate", "collect", "resume", "status", "export", "diagnostics",
    "live_check", "review_import", "live_report",
)


@pytest.mark.parametrize("command", COMMANDS)
def test_bat_is_thin_root_relative_and_preserves_exit_code(command: str) -> None:
    content = (ROOT / f"{command}.bat").read_text(encoding="utf-8")
    assert "%~dp0" in content
    assert "powershell.exe" in content
    assert f"scripts\\windows\\{command}.ps1" in content
    assert "exit /b %EXIT_CODE%" in content
    assert "pip install" not in content


def test_common_script_handles_python_paths_logs_and_pause() -> None:
    content = (ROOT / "scripts/windows/common.ps1").read_text(encoding="utf-8")
    expected_values = (
        "Find-Python313", ".venv\\Scripts\\python.exe", "Start-Transcript", "PauseOnExit"
    )
    for expected in expected_values:
        assert expected in content


def test_reset_requires_confirmation_and_setup_preserves_input() -> None:
    reset = (ROOT / "reset_retries.bat").read_text(encoding="utf-8")
    setup = (ROOT / "scripts/windows/setup.ps1").read_text(encoding="utf-8")
    assert "[Y/N]" in reset and 'not "%ANSWER%"=="Y"' in reset
    assert "-not (Test-Path -LiteralPath $actual)" in setup
    assert "playwright install chromium" in setup
