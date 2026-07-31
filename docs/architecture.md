# Architecture

## Principles

The system uses responsibility-based modules and keeps dependencies flowing from orchestration toward small infrastructure components. Search, crawl, extraction, scoring, persistence, and export are independent so that changes to an external search site do not affect stored data or extraction rules.

## Module boundaries

- `search/providers`: replaceable free search providers. `query_builder` creates queries and `result_parser` normalizes provider output.
- `crawler`: robots.txt policy, per-origin rate limiting, raw HTTP fetching, transport results, and an injectable Playwright fallback. It does not parse HTML.
- `extractor`: separate JSON-LD, schema.org, company, address, phone, and industry extraction coordinated by a facade. Every value retains its source.
- `storage`: SQLite lifecycle/migrations and resumable progress state.
- `scoring`: excluded-domain and page-type classification followed by configurable, auditable official-site and business-target scores.
- `export`: CSV and Excel presentation without persistence concerns.
- `utils`: configuration and logging infrastructure only.

Phase 3 implements search query construction, the provider contract, Bing RSS, and provider orchestration. Yahoo, DuckDuckGo, Mojeek, and Bing HTML remain unimplemented. The crawler remains a boundary without behavior, so destination company sites are never fetched in this phase.

## Runtime data flow

Future phases will follow: search query → provider results → crawl queue → fetched pages → extracted facts → official-site and business scoring → SQLite → export. Progress checkpoints are persisted independently so interrupted work can be returned to the pending queue safely.

Phase 7の`pipeline`は、この依存方向を変えずに各Facadeを調整します。CoordinatorだけがQueryBuilderとSearchManagerを呼び、CandidateProcessorだけがFetcher、ExtractorFacade、ScoringFacade、PipelineRepositoryを順番に接続します。

Phase 8の`export`と`status`はSQLiteを唯一の入力とします。ExportServiceは一度のスナップショットからCSVとExcelを直接生成し、CLIだけが結果を表示します。

## SQLite and Resume

`Database` owns connection configuration, transactions, and monotonic schema migrations. `ProgressStore` owns task lifecycle transitions. A task key is unique, claims are atomic, cursors survive restarts, and only tasks left `running` by an interruption are reset to `pending`. Completed and failed tasks are not silently retried.

## Configuration and logging

Safe defaults live in `default.yaml`; industries, excluded domains, and provider order use dedicated operator-editable files. Overrides merge recursively, but robots.txt compliance cannot be disabled. Logs use UTF-8 rotating files to prevent unbounded growth.
