"""Phase 9 Step 2 search-condition CSV tests."""

from pathlib import Path

import pytest

from application.input import InputMode, InputValidationError, SearchConditionReader

HEADER = "都道府県,市区町村,検索業種,最大取得件数,有効,備考\n"


def test_reads_utf8_bom_and_normalizes_full_width_values(tmp_path: Path) -> None:
    path = tmp_path / "conditions.csv"
    path.write_text(
        HEADER + " 東京都 , 千代田区 , 建設業 ,\uff15,はい, test \n",
        encoding="utf-8-sig",
    )

    result = SearchConditionReader(InputMode.STRICT).read(path)

    assert len(result.conditions) == 1
    assert result.conditions[0].condition.max_results == 5
    assert result.conditions[0].condition.enabled is True
    assert result.conditions[0].note == "test"
    assert result.encoding == "utf-8-sig"


def test_reads_cp932_and_japanese_false(tmp_path: Path) -> None:
    path = tmp_path / "conditions.csv"
    path.write_bytes((HEADER + "大阪府,大阪市,美容業,3,無効,\n").encode("cp932"))

    result = SearchConditionReader(InputMode.STRICT).read(path)

    assert result.encoding == "cp932"
    assert result.conditions[0].condition.enabled is False


def test_strict_stops_and_lenient_continues_with_row_number(tmp_path: Path) -> None:
    path = tmp_path / "conditions.csv"
    path.write_text(
        HEADER + "東京都,千代田区,建設業,2,はい,\n東京都,中央区,建設業,不正,はい,\n",
        encoding="utf-8",
    )

    with pytest.raises(InputValidationError) as caught:
        SearchConditionReader(InputMode.STRICT).read(path)
    assert caught.value.issues[0].row_number == 3

    result = SearchConditionReader(InputMode.LENIENT).read(path)
    assert len(result.conditions) == 1
    assert result.issues[0].row_number == 3


def test_duplicate_condition_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "conditions.csv"
    path.write_text(
        HEADER + "東京都,千代田区,建設業,2,はい,\n東京都,千代田区,建設業,3,はい,\n",
        encoding="utf-8",
    )

    with pytest.raises(InputValidationError, match="重複"):
        SearchConditionReader(InputMode.STRICT).read(path)
