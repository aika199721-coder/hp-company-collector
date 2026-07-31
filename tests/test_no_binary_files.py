"""Guard the pull-request tree against unsupported binary files."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARY_SUFFIXES = {
    ".bin", ".dll", ".exe", ".gif", ".gz", ".ico", ".jpeg", ".jpg",
    ".pdf", ".png", ".ttf", ".webp", ".woff", ".woff2", ".xls", ".xlsx", ".zip",
}


def test_all_git_managed_files_are_utf8_text() -> None:
    """Require fixtures and other PR content to remain UTF-8 text."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    binary_files: list[str] = []
    for relative in result.stdout.splitlines():
        path = ROOT / relative
        if not path.exists():
            continue
        data = path.read_bytes()
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            binary_files.append(relative)
        if path.suffix.lower() in BINARY_SUFFIXES:
            binary_files.append(relative)
    assert binary_files == []
