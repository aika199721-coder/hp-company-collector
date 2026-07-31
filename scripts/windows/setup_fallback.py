"""Python-only setup fallback for Windows hosts that deny PowerShell script access."""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


def main() -> int:
    """Create the virtual environment, install dependencies, and validate configuration."""
    root = Path(__file__).resolve().parents[2]
    for name in ("logs", "data", "input", "output"):
        (root / name).mkdir(parents=True, exist_ok=True)
    log = root / "logs" / f"setup_fallback_{datetime.now():%Y%m%d_%H%M%S}.log"
    try:
        if sys.version_info[:2] != (3, 13):
            return _write(log, "Python 3.13が必要です。", 2)
        messages = [f"Python: {sys.executable}", f"bit数: {struct.calcsize('P') * 8}"]
        venv = root / ".venv"
        python = venv / "Scripts" / "python.exe"
        if not python.exists():
            _run([sys.executable, "-m", "venv", str(venv)], root, messages)
        _run([str(python), "-m", "pip", "install", "--upgrade", "pip"], root, messages)
        _run(
            [str(python), "-m", "pip", "install", "-r", str(root / "requirements.txt")],
            root,
            messages,
        )
        actual = root / "input" / "search_conditions.csv"
        if not actual.exists():
            shutil.copy2(root / "input" / "search_conditions_sample.csv", actual)
        _run([str(python), "-m", "src.cli", "validate"], root, messages)
        return _write(log, "\n".join([*messages, "セットアップ完了"]), 0)
    except Exception:
        return _write(log, traceback.format_exc(), 1)


def _run(command: list[str], root: Path, messages: list[str]) -> None:
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    messages.extend((f"> {' '.join(command)}", completed.stdout, completed.stderr))
    if completed.returncode:
        raise RuntimeError(f"終了コード {completed.returncode}: {command[2:]}")


def _write(log: Path, message: str, code: int) -> int:
    print(message)
    print(f"セットアップログ: {log}")
    log.write_text(message, encoding="utf-8")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
