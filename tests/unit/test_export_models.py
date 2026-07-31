"""Phase 8 Step 1 export model tests."""

from export.models import ExportCategory


def test_required_export_categories_are_defined() -> None:
    assert {item.value for item in ExportCategory} == {
        "all_results",
        "business_targets",
        "mobile_only",
        "no_phone",
        "review_required",
        "excluded",
        "errors",
    }


def test_sales_rows_deduplicate_url_but_history_remains(populated_database) -> None:
    """One sales row represents repeated URL discoveries while all history remains."""
    from export.repository import ExportRepository

    with populated_database.connect() as connection:
        condition = connection.execute(
            """
            INSERT INTO search_conditions(
                prefecture, municipality, industry, max_results, enabled, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("東京都", "中央区", "建設業", 10, 1, "completed"),
        ).lastrowid
        query = connection.execute(
            "INSERT INTO search_queries(condition_id, query) VALUES (?, ?)",
            (condition, "duplicate query"),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO search_results(query_id, url, provider, rank, title, snippet)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (query, "https://mobile.example/", "fake", 1, "duplicate", ""),
        )

    snapshot = ExportRepository(populated_database).read_snapshot()

    assert len(snapshot.rows) == 6
    assert len(snapshot.rows_for(ExportCategory.BUSINESS_TARGETS)) == 2
    mobile = snapshot.rows_for(ExportCategory.BUSINESS_TARGETS)[0]
    assert mobile.duplicate_candidate is True
    assert "千代田区" in mobile.all_search_conditions
    assert "中央区" in mobile.all_search_conditions
