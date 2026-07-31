"""Shared offline test fixtures."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from scoring.facade import ScoringFacade

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def scoring_config() -> dict[str, Any]:
    """Load the repository scoring fixture configuration."""
    return yaml.safe_load((ROOT / "config/scoring.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def scoring_facade(scoring_config: dict[str, Any]) -> ScoringFacade:
    """Build a scoring facade using repository offline configuration."""
    return ScoringFacade(
        scoring_config,
        exclude_domains_path=ROOT / "config/exclude_domains.txt",
    )


@pytest.fixture
def populated_database(tmp_path: Path):
    """Create a temporary SQLite export/status fixture with all output categories."""
    from storage.sqlite import Database

    database = Database(tmp_path / "export.sqlite3")
    database.initialize()
    with database.connect() as connection:
        condition = connection.execute(
            """
            INSERT INTO search_conditions(
                prefecture, municipality, industry, max_results, enabled, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("東京都", "千代田区", "建設業", 10, 1, "completed"),
        ).lastrowid
        connection.executemany(
            """
            INSERT INTO search_conditions(
                prefecture, municipality, industry, max_results, enabled, status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("東京都", "中央区", "建設業", 10, 1, "pending"),
                ("大阪府", "大阪市", "建設業", 10, 1, "processing"),
            ],
        )
        query = connection.execute(
            "INSERT INTO search_queries(condition_id, query) VALUES (?, ?)",
            (condition, '"東京都" "千代田区" "建設業" 公式サイト'),
        ).lastrowid
        rows = [
            ("https://mobile.example/", "success", 200, True, True, False),
            ("https://no-phone.example/", "success", 200, True, True, False),
            ("https://review.example/", "excluded", 200, True, False, True),
            ("https://excluded.example/", "excluded", 200, False, False, False),
            ("https://error.example/", "scoring_failed", 200, False, False, False),
        ]
        for rank, (url, status, http, official, target, review) in enumerate(rows, 1):
            search_result = connection.execute(
                """
                INSERT INTO search_results(query_id, url, provider, rank, title, snippet)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (query, url, "fake", rank, f"title-{rank}", "snippet"),
            ).lastrowid
            assert search_result is not None
            page = connection.execute(
                """
                INSERT INTO pages(
                    url, final_url, http_status, processing_status, fetched_at, updated_at
                ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (url, url + "about", http, status),
            ).lastrowid
            company = connection.execute(
                """
                INSERT INTO companies(
                    page_id, company_name, store_name, display_name, industry
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (page, f"株式会社{rank}", f"店舗{rank}", f"表示{rank}", "建設業"),
            ).lastrowid
            connection.execute(
                """
                INSERT INTO addresses(
                    company_id, address, postal_code, prefecture, municipality, source
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (company, "東京都千代田区1-1", "001-0001", "東京都", "千代田区", "fixture"),
            )
            if rank == 1:
                connection.executemany(
                    """
                    INSERT INTO phones(company_id, number, kind, usage, source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (company, "090-1234-5678", "mobile", "reservation", "fixture"),
                        (company, "03-1234-5678", "fixed", "main", "fixture"),
                    ],
                )
            elif rank > 2:
                connection.execute(
                    """
                    INSERT INTO phones(company_id, number, kind, usage, source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (company, "03-0000-0000", "fixed", "main", "fixture"),
                )
            connection.execute(
                """
                INSERT INTO scoring_results(
                    page_id, official_score, business_score, is_official,
                    is_business_target, review_required, reasons_json,
                    positive_signals_json, negative_signals_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    page,
                    80 if official else 20,
                    70 if target else 20,
                    int(official),
                    int(target),
                    int(review),
                    '["判定理由"]',
                    '["加点"]',
                    '["減点"]' if not target else "[]",
                ),
            )
            if rank == 5:
                connection.execute(
                    """
                    INSERT INTO processing_errors(page_id, error_type, message)
                    VALUES (?, ?, ?)
                    """,
                    (page, "scoring_error", "fixture failure"),
                )
        connection.executemany(
            """
            INSERT INTO progress(task_key, payload, status, available_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    "https://retry.example/",
                    '{"candidate":{"url":"https://retry.example/"}}',
                    "pending",
                    "2099-01-01 00:00:00",
                ),
                (
                    "https://running.example/",
                    '{"candidate":{"url":"https://running.example/"}}',
                    "running",
                    None,
                ),
            ],
        )
    return database
