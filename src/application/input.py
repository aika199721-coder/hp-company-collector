"""Multi-encoding search-condition CSV validation and normalization."""

from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from pipeline.models import SearchCondition

_REQUIRED_COLUMNS = ("都道府県", "市区町村", "検索業種", "最大取得件数", "有効")
_TRUE_VALUES = {"true", "1", "yes", "y", "はい", "有効", "対象", "含める"}
_FALSE_VALUES = {"false", "0", "no", "n", "いいえ", "無効", "対象外", "含めない"}


class InputMode(StrEnum):
    """Invalid-row handling mode."""

    STRICT = "strict"
    LENIENT = "lenient"


@dataclass(frozen=True, slots=True)
class InputIssue:
    """One row-numbered, user-correctable input error."""

    row_number: int
    message: str


class InputValidationError(ValueError):
    """Raised in strict mode when any CSV issue exists."""

    def __init__(self, issues: tuple[InputIssue, ...]) -> None:
        self.issues = issues
        detail = "; ".join(f"row {item.row_number}: {item.message}" for item in issues)
        super().__init__(detail)


@dataclass(frozen=True, slots=True)
class SearchConditionRecord:
    """Pipeline condition plus optional per-row application controls."""

    condition: SearchCondition
    max_candidates: int | None
    count_no_phone_as_target: bool | None
    additional_keywords: tuple[str, ...]
    excluded_keywords: tuple[str, ...]
    note: str
    row_number: int


@dataclass(frozen=True, slots=True)
class SearchConditionInput:
    """Validated records, issues, and detected source encoding."""

    conditions: tuple[SearchConditionRecord, ...]
    issues: tuple[InputIssue, ...]
    encoding: str


class SearchConditionReader:
    """Read UTF-8 BOM, UTF-8, or CP932 CSV without silent replacement."""

    def __init__(self, mode: InputMode = InputMode.STRICT) -> None:
        self.mode = mode

    def read(self, path: Path) -> SearchConditionInput:
        """Validate all rows and either reject or retain valid records."""
        path = Path(path)
        try:
            content = path.read_bytes()
        except OSError as exc:
            issue = InputIssue(0, f"入力ファイルを読めません: {path}")
            raise InputValidationError((issue,)) from exc
        text, encoding = _decode(content)
        reader = csv.DictReader(io.StringIO(text, newline=""))
        columns = tuple((name or "").strip() for name in (reader.fieldnames or ()))
        missing = [name for name in _REQUIRED_COLUMNS if name not in columns]
        if missing:
            issue = InputIssue(1, f"必須列がありません: {', '.join(missing)}")
            raise InputValidationError((issue,))

        records: list[SearchConditionRecord] = []
        issues: list[InputIssue] = []
        seen: set[tuple[str, str, str]] = set()
        for row_number, raw in enumerate(reader, 2):
            row = {str(key).strip(): str(value or "").strip() for key, value in raw.items()}
            if not any(row.values()):
                continue
            try:
                record = _record(row, row_number)
                key = (
                    record.condition.prefecture,
                    record.condition.municipality,
                    record.condition.industry,
                )
                if key in seen:
                    raise ValueError("重複した検索条件です")
                seen.add(key)
                records.append(record)
            except (TypeError, ValueError) as exc:
                issues.append(InputIssue(row_number, str(exc)))
        if issues and self.mode is InputMode.STRICT:
            raise InputValidationError(tuple(issues))
        return SearchConditionInput(tuple(records), tuple(issues), encoding)


def _decode(content: bytes) -> tuple[str, str]:
    if content.startswith(b"\xef\xbb\xbf"):
        return content.decode("utf-8-sig"), "utf-8-sig"
    for encoding in ("utf-8", "cp932"):
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise InputValidationError((InputIssue(0, "UTF-8またはCP932として読めません"),))


def _record(row: dict[str, str], row_number: int) -> SearchConditionRecord:
    maximum = _positive_integer(row["最大取得件数"], "最大取得件数")
    condition = SearchCondition(
        row["都道府県"].strip(),
        row["市区町村"].strip(),
        row["検索業種"].strip(),
        maximum,
        _boolean(row["有効"], "有効"),
    )
    candidate_text = row.get("最大候補処理件数", "")
    no_phone_text = row.get("電話番号なしを件数に含める", "")
    return SearchConditionRecord(
        condition,
        _positive_integer(candidate_text, "最大候補処理件数") if candidate_text else None,
        _boolean(no_phone_text, "電話番号なしを件数に含める") if no_phone_text else None,
        _keywords(row.get("検索キーワード追加", "")),
        _keywords(row.get("除外キーワード", "")),
        row.get("備考", "").strip(),
        row_number,
    )


def _positive_integer(value: str, label: str) -> int:
    normalized = unicodedata.normalize("NFKC", value).strip()
    try:
        number = int(normalized)
    except ValueError as exc:
        raise ValueError(f"{label}は正の整数で指定してください") from exc
    if number < 1:
        raise ValueError(f"{label}は正の整数で指定してください")
    return number


def _boolean(value: str, label: str) -> bool:
    normalized = unicodedata.normalize("NFKC", value).strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"{label}の真偽値が不正です: {value}")


def _keywords(value: str) -> tuple[str, ...]:
    normalized = value.replace("、", "|").replace(",", "|")
    return tuple(item.strip() for item in normalized.split("|") if item.strip())
