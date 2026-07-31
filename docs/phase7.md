# Phase 7 — Integration pipeline

## Processing flow

The single-worker flow is: `SearchCondition` → `QueryBuilder` → `SearchManager` → discovery history and unique progress tasks → atomic claim → `Fetcher` → HTTP state check → `ExtractorFacade` → `ScoringFacade` → transactional SQLite persistence. CSV, Excel, Windows batch files, schedules, and parallel workers remain out of scope.

## State transitions

- `pending → running → completed`: success, scoring exclusion, robots denial, 403, or 404.
- `pending → running → pending(available_at)`: 429, 503, timeout, or retryable transport failure.
- `pending → running → failed`: extraction, scoring, invalid payload, or unexpected processing failure.
- An already terminal URL is not fetched again; another search condition still records its discovery.

`ProcessingStatus` distinguishes success, business exclusion, duplicate, robots denial, each required HTTP status, timeout, transport error, extraction failure, scoring failure, and unexpected failure.

## SQLite relationships

`search_conditions → search_queries → search_results` preserves every discovery, including the same URL under another condition. `pages` owns raw transport data and one URL identity. `companies` is separate from pages and owns multiple `phones` and `addresses`. `scoring_results` stores both scores, booleans, reasons, and positive/negative signals as JSON. `processing_errors` retains per-task failures. The original `progress` table remains the work queue. All writes use placeholders and transactional `Database.connect()` connections; schema version 2 keeps WAL mode.

## Resume design

At coordinator startup, interrupted `running` tasks return to `pending`. Claims use one atomic SQLite `UPDATE ... RETURNING`. Each claimed task saves a rank cursor before processing. Unique normalized URL task keys prevent duplicate fetches, while search result rows preserve discovery history. Terminal pages are not fetched again.

## Retry and domain pause design

Retryable tasks receive `available_at`; claims skip them until that UTC time. HTTP 429 honors numeric or HTTP-date `Retry-After`, with a configured fallback delay. 429, 503, timeout, and transport failures persist an origin-wide stop time. Another URL on the same origin is deferred without an HTTP request. Non-retryable robots denial, 403, and 404 complete explicitly.

## Error classification

Transport, HTTP, extraction, scoring, payload, and unexpected errors remain distinct. Partial page or extraction data is saved before a later-stage failure. Low scores, hard exclusions, and missing phone numbers are normal persisted results rather than exceptions. One candidate failure is caught so the next claimed task continues.

## Next-phase review

1. Review retry limits and a policy for permanently failing repeated retries.
2. Decide retention and size limits for raw page bodies.
3. Review schema normalization if multiple companies or addresses per page become necessary.
4. Define CSV/Excel columns without embedding export concerns in the pipeline.
5. Review Windows setup/run commands and operator-facing cancellation before implementing them.
