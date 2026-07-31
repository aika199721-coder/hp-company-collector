"""Dynamic Windows PowerShell 5.1 regressions for Python probing."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    os.name != "nt" or sys.version_info[:2] != (3, 13),
    reason="requires Windows and the Python 3.13 CI interpreter",
)
def test_powershell51_probes_empty_launcher_and_hpcc_prefixes(tmp_path: Path) -> None:
    """Run real Windows PowerShell 5.1 probes, including a Japanese path."""
    japanese_root = tmp_path / "日本語パス"
    japanese_root.mkdir()
    broken_probe = japanese_root / "broken-python.cmd"
    broken_probe.write_text("@echo off\r\necho fake.exe\r\necho 3.13\r\necho invalid-bits\r\n")
    failed_probe = japanese_root / "failed-python.cmd"
    failed_probe.write_text("@echo off\r\necho probe-stderr 1>&2\r\nexit /b 7\r\n")
    script = japanese_root / "probe.ps1"
    common = ROOT / "scripts" / "windows" / "common.ps1"
    script.write_text(
        "\n".join(
            (
                "$utf8 = New-Object System.Text.UTF8Encoding($false)",
                "[Console]::OutputEncoding = $utf8",
                "$script:OutputEncoding = $utf8",
                f". '{_powershell_literal(common)}'",
                f"$env:HPCC_PYTHON = '{_powershell_literal(Path(sys.executable))}'",
                "$empty = [pscustomobject]@{ Exe = $env:HPCC_PYTHON; Prefix = @(); "
                "Source = 'HPCC_PYTHON' }",
                "$emptyResult = Test-PythonCandidate -Candidate $empty",
                "if ($null -eq $emptyResult) { throw 'empty Prefix probe failed' }",
                "if ($emptyResult.Path -ne $env:HPCC_PYTHON) { throw 'absolute path mismatch' }",
                "$launcher = [pscustomobject]@{ Exe = 'py'; Prefix = @('-3.13'); "
                "Source = 'py -3.13' }",
                "$launcherResult = Test-PythonCandidate -Candidate $launcher",
                "if ($null -eq $launcherResult) { throw 'py -3.13 probe failed' }",
                f"$broken = [pscustomobject]@{{ Exe = '{_powershell_literal(broken_probe)}'; "
                "Prefix = @(); Source = 'broken' }",
                "$brokenResult = Test-PythonCandidate -Candidate $broken",
                "if ($null -ne $brokenResult) { throw 'broken probe was accepted' }",
                f"$failed = [pscustomobject]@{{ Exe = '{_powershell_literal(failed_probe)}'; "
                "Prefix = @(); Source = 'failed' }",
                "$failedResult = Test-PythonCandidate -Candidate $failed",
                "if ($null -ne $failedResult) { throw 'failed probe was accepted' }",
                "Write-Host 'DYNAMIC_PROBE_OK'",
            )
        ),
        encoding="utf-8-sig",
    )

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
        ],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        text=True,
    )

    output = (completed.stdout or "") + (completed.stderr or "")
    assert completed.returncode == 0, output
    assert output.count("version=3.13 bits=64") == 2
    assert "Python候補 [HPCC_PYTHON]" in output
    assert "Python候補 [py -3.13]" in output
    assert "Python候補の検証例外 [broken]" in output
    assert "Python候補のprobe失敗 [failed]" in output
    assert "exit=7 output=probe-stderr" in output
    assert "DYNAMIC_PROBE_OK" in output


def _powershell_literal(path: Path) -> str:
    """Escape a path for a PowerShell single-quoted string."""
    return str(path.resolve()).replace("'", "''")
