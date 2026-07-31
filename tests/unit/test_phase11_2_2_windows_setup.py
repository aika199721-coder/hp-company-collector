"""Regression gates for the frozen Phase 11.2.2 Windows setup distribution."""

from pathlib import Path
from types import MappingProxyType

from application.collection import _summary_dict
from pipeline.models import PipelineSummary

ROOT = Path(__file__).resolve().parents[2]
MARKER = "setupfix11.2.2.2-v1"


def test_canonical_launchers_are_marked_and_obsolete_invocations_are_absent() -> None:
    files = (
        "setup.bat",
        "validate.bat",
        "live_check.bat",
        "scripts/windows/setup.ps1",
        "scripts/windows/common.ps1",
        "scripts/windows/validate.ps1",
        "scripts/windows/live_check.ps1",
    )
    for relative in files:
        content = (ROOT / relative).read_text(encoding="utf-8-sig")
        assert MARKER in content
        assert "cmdcmdline" not in content.lower()
        assert "^&" not in content


def test_setup_batch_keeps_screen_and_has_access_denied_fallback() -> None:
    content = (ROOT / "setup.bat").read_text(encoding="utf-8-sig")
    assert "Unblock-File" in content
    assert "setup_fallback.py" in content
    assert "Press any key to continue" in content
    assert "終了コード" in content
    assert "validate.bat" in content
    assert "logs" in content
    assert "--no-pause" in content


def test_powershell_is_51_safe_and_native_stderr_does_not_become_exception() -> None:
    common = (ROOT / "scripts/windows/common.ps1").read_text(encoding="utf-8-sig")
    setup = (ROOT / "scripts/windows/setup.ps1").read_text(encoding="utf-8-sig")
    assert "PSNativeCommandUseErrorActionPreference = $false" in common
    assert "New-Object System.Text.UTF8Encoding" in common
    assert "[int]$code" in common and "exit ([int]$code)" in common
    assert "struct.calcsize(\"P\")" in setup
    assert "struct.calcsize(\\\"P\\\")" not in setup


def test_all_powershell_files_use_utf8_bom_and_crlf() -> None:
    for path in (ROOT / "scripts/windows").glob("*.ps1"):
        content = path.read_bytes()
        assert content.startswith(b"\xef\xbb\xbf"), path
        assert b"\n" not in content[3:].replace(b"\r\n", b""), path


def test_summary_serialization_does_not_recurse_into_mappingproxy_results() -> None:
    unsafe_result = MappingProxyType({"headers": MappingProxyType({"x": "y"})})
    summary = PipelineSummary(1, 1, 0, 0, 1, 0, 0, 0, 0, {}, (unsafe_result,))

    serialized = _summary_dict(summary)

    assert serialized["candidate_count"] == 1
    assert "results" not in serialized


def test_workflow_requires_windows_setup_smoke_before_artifact_publish() -> None:
    workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    for value in ("日本語パス", "space path", "括弧 (test)", "OneDrive - Company"):
        assert value in workflow
    assert "needs: [python, windows-setup-smoke]" in workflow
    assert "setup.bat') --no-pause" in workflow
    assert "validate.bat') --no-pause" in workflow
    assert "setup rerun failed" in workflow
    assert "HPCC_PYTHON: ${{ steps.setup_python.outputs.python-path }}" in workflow


def test_powershell_detection_contains_required_priority_and_probe() -> None:
    common = (ROOT / "scripts/windows/common.ps1").read_text(encoding="utf-8-sig")
    ordered = (
        "$env:HPCC_PYTHON",
        "Get-Command python.exe",
        "where.exe python",
        "$env:pythonLocation",
        "$env:Python_ROOT_DIR",
        ".venv\\Scripts\\python.exe",
        "-Exe 'py'",
        "-Exe 'python'",
        "-Exe 'python3'",
    )
    positions = [common.index(value) for value in ordered]
    assert positions == sorted(positions)
    assert "struct.calcsize(\"P\") * 8" in common
    assert "\\WindowsApps\\" in common
    assert "$version -ne '3.13' -or $bits -ne 64" in common


def test_powershell_candidate_collection_accepts_and_wraps_empty_arrays() -> None:
    common = (ROOT / "scripts/windows/common.ps1").read_text(encoding="utf-8-sig")
    function = common.split("function Get-PythonCandidates", 1)[1].split(
        "function Test-PythonCandidate", 1
    )[0]

    assert "[AllowEmptyCollection()]" in common
    assert "return @($candidates.ToArray())" in function
    assert "$candidates = @(Get-PythonCandidates -Root $Root)" in common
    assert "Python 3.13候補が見つかりません" in common
    assert "Write-Output" not in function
