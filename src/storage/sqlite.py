"""SQLite connection lifecycle and schema migrations."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA_VERSION = 6


class Database:
    """Own SQLite connections and apply versioned, transactional migrations."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        """Create the database and upgrade its schema to the current version."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database schema {version} is newer than supported {SCHEMA_VERSION}"
                )
            if version < 1:
                connection.executescript(
                    """
                    CREATE TABLE progress (
                        id INTEGER PRIMARY KEY,
                        task_key TEXT NOT NULL UNIQUE,
                        payload TEXT NOT NULL DEFAULT '{}',
                        status TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'running', 'completed', 'failed')),
                        cursor TEXT,
                        attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
                        last_error TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX progress_status_id_idx ON progress(status, id);
                    PRAGMA user_version = 1;
                    """
                )
                version = 1
            if version < 2:
                connection.executescript(
                    """
                    ALTER TABLE progress ADD COLUMN available_at TEXT;
                    CREATE TABLE search_conditions (
                        id INTEGER PRIMARY KEY,
                        prefecture TEXT NOT NULL,
                        municipality TEXT NOT NULL,
                        industry TEXT NOT NULL,
                        max_results INTEGER NOT NULL,
                        enabled INTEGER NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE search_queries (
                        id INTEGER PRIMARY KEY,
                        condition_id INTEGER NOT NULL REFERENCES search_conditions(id),
                        query TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(condition_id, query)
                    );
                    CREATE TABLE search_results (
                        id INTEGER PRIMARY KEY,
                        query_id INTEGER NOT NULL REFERENCES search_queries(id),
                        url TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        rank INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        snippet TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(query_id, url)
                    );
                    CREATE TABLE pages (
                        id INTEGER PRIMARY KEY,
                        url TEXT NOT NULL UNIQUE,
                        final_url TEXT,
                        http_status INTEGER,
                        headers_json TEXT NOT NULL DEFAULT '{}',
                        content BLOB,
                        encoding TEXT,
                        fetch_error TEXT,
                        processing_status TEXT NOT NULL,
                        fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE companies (
                        id INTEGER PRIMARY KEY,
                        page_id INTEGER NOT NULL UNIQUE REFERENCES pages(id),
                        company_name TEXT,
                        store_name TEXT,
                        display_name TEXT,
                        industry TEXT
                    );
                    CREATE TABLE phones (
                        id INTEGER PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES companies(id),
                        number TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        usage TEXT NOT NULL,
                        source TEXT NOT NULL,
                        UNIQUE(company_id, number)
                    );
                    CREATE TABLE addresses (
                        id INTEGER PRIMARY KEY,
                        company_id INTEGER NOT NULL REFERENCES companies(id),
                        address TEXT NOT NULL,
                        postal_code TEXT,
                        prefecture TEXT,
                        municipality TEXT,
                        source TEXT NOT NULL,
                        UNIQUE(company_id, address)
                    );
                    CREATE TABLE scoring_results (
                        id INTEGER PRIMARY KEY,
                        page_id INTEGER NOT NULL UNIQUE REFERENCES pages(id),
                        official_score INTEGER NOT NULL,
                        business_score INTEGER NOT NULL,
                        is_official INTEGER NOT NULL,
                        is_business_target INTEGER NOT NULL,
                        review_required INTEGER NOT NULL,
                        reasons_json TEXT NOT NULL,
                        positive_signals_json TEXT NOT NULL,
                        negative_signals_json TEXT NOT NULL
                    );
                    CREATE TABLE processing_errors (
                        id INTEGER PRIMARY KEY,
                        page_id INTEGER REFERENCES pages(id),
                        progress_id INTEGER REFERENCES progress(id),
                        error_type TEXT NOT NULL,
                        message TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE domain_pauses (
                        origin TEXT PRIMARY KEY,
                        paused_until TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX search_results_url_idx ON search_results(url);
                    PRAGMA user_version = 2;
                    """
                )
                version = 2
            if version < 3:
                connection.executescript(
                    """
                    ALTER TABLE search_conditions
                    ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processing', 'completed'));
                    ALTER TABLE search_conditions ADD COLUMN completed_at TEXT;
                    PRAGMA user_version = 3;
                    """
                )
                version = 3
            if version < 4:
                connection.executescript(
                    """
                    CREATE TABLE runs (
                        run_id TEXT PRIMARY KEY,
                        command TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        finished_at TEXT,
                        status TEXT NOT NULL,
                        input_file TEXT NOT NULL,
                        config_file TEXT NOT NULL,
                        database_file TEXT NOT NULL,
                        conditions_total INTEGER NOT NULL DEFAULT 0,
                        conditions_completed INTEGER NOT NULL DEFAULT 0,
                        business_targets INTEGER NOT NULL DEFAULT 0,
                        processed_candidates INTEGER NOT NULL DEFAULT 0,
                        error_count INTEGER NOT NULL DEFAULT 0,
                        shutdown_reason TEXT,
                        application_version TEXT NOT NULL
                    );
                    CREATE TABLE run_conditions (
                        id INTEGER PRIMARY KEY,
                        run_id TEXT NOT NULL REFERENCES runs(run_id),
                        condition_index INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        summary_json TEXT NOT NULL DEFAULT '{}',
                        error_message TEXT,
                        started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        finished_at TEXT,
                        UNIQUE(run_id, condition_index)
                    );
                    CREATE TABLE shutdown_events (
                        id INTEGER PRIMARY KEY,
                        run_id TEXT NOT NULL REFERENCES runs(run_id),
                        reason TEXT NOT NULL,
                        signal_name TEXT,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    PRAGMA user_version = 4;
                    """
                )
                version = 4
            if version < 5:
                connection.executescript(
                    """
                    CREATE TABLE http_audit_logs (
                        id INTEGER PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        requested_url TEXT NOT NULL,
                        final_url TEXT NOT NULL,
                        domain TEXT NOT NULL,
                        requested_at TEXT NOT NULL,
                        finished_at TEXT NOT NULL,
                        elapsed_ms INTEGER NOT NULL,
                        http_status INTEGER,
                        content_type TEXT,
                        content_length INTEGER NOT NULL,
                        encoding TEXT,
                        redirect_count INTEGER NOT NULL,
                        robots_allowed INTEGER NOT NULL,
                        rate_limit_delay REAL NOT NULL,
                        playwright_used INTEGER NOT NULL,
                        result_category TEXT NOT NULL,
                        error_type TEXT
                    );
                    CREATE INDEX http_audit_run_idx ON http_audit_logs(run_id, id);
                    CREATE TABLE manual_reviews (
                        id INTEGER PRIMARY KEY,
                        url TEXT NOT NULL,
                        company_name_judgment TEXT NOT NULL,
                        store_name_judgment TEXT NOT NULL,
                        phone_judgment TEXT NOT NULL,
                        address_judgment TEXT NOT NULL,
                        industry_judgment TEXT NOT NULL,
                        official_site_judgment TEXT NOT NULL,
                        business_target_judgment TEXT NOT NULL,
                        overall_judgment TEXT NOT NULL,
                        note TEXT NOT NULL,
                        reviewer TEXT,
                        reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE INDEX manual_reviews_url_idx ON manual_reviews(url, reviewed_at);
                    PRAGMA user_version = 5;
                    """
                )
                version = 5
            if version < 6:
                connection.executescript(
                    """
                    ALTER TABLE search_results ADD COLUMN relevance_score REAL NOT NULL DEFAULT 0;
                    ALTER TABLE search_results ADD COLUMN normalized_url TEXT NOT NULL DEFAULT '';
                    UPDATE search_results SET normalized_url = LOWER(RTRIM(url, '/'));
                    CREATE TABLE search_provider_audit (
                        id INTEGER PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        query TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        enabled INTEGER NOT NULL,
                        started_at TEXT NOT NULL,
                        finished_at TEXT NOT NULL,
                        http_status INTEGER,
                        result_count INTEGER NOT NULL,
                        accepted_count INTEGER NOT NULL,
                        duplicate_count INTEGER NOT NULL,
                        failure_type TEXT,
                        failure_message TEXT,
                        final_url TEXT,
                        elapsed_ms INTEGER NOT NULL
                    );
                    CREATE INDEX search_provider_audit_run_idx
                    ON search_provider_audit(run_id, id);
                    DELETE FROM processing_errors WHERE error_type = 'prefetch_excluded';
                    PRAGMA user_version = 6;
                    """
                )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a configured connection and commit or roll back atomically."""
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
