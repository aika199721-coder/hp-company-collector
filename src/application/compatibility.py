"""Runtime compatibility checks shared by CLI and Windows setup."""

from __future__ import annotations

import struct
import sys
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeCompatibility:
    """Python version and architecture compatibility result."""

    supported: bool
    is_64bit: bool
    message: str


def check_runtime(
    version: tuple[int, int] | None = None, pointer_bits: int | None = None
) -> RuntimeCompatibility:
    """Require Python 3.13 and recommend a 64-bit interpreter."""
    actual_version = version or sys.version_info[:2]
    actual_bits = pointer_bits or struct.calcsize("P") * 8
    if actual_version != (3, 13):
        return RuntimeCompatibility(
            False,
            actual_bits == 64,
            f"Python 3.13 が必要です (検出: {actual_version[0]}.{actual_version[1]})。",
        )
    if actual_bits != 64:
        return RuntimeCompatibility(True, False, "Python 3.13 64bit版を推奨します。")
    return RuntimeCompatibility(True, True, "Python 3.13 64bitを確認しました。")
