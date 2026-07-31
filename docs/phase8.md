# Phase 8 — Export, status, and minimal CLI

## CSV specification

CSV uses UTF-8 with BOM and CRLF. Phone and postal values remain text so leading zeroes are retained. `collected_companies.csv` contains business targets; separate files contain mobile, no-phone, review-required, excluded, and error rows. Multiple phones are split into primary, mobile, fixed, usage, and delimiter-joined all-number columns.

## Excel sheets

The workbook always contains 営業対象, 携帯あり, 要確認, 電話なし, 除外, エラー, and 全件 in that order, even when a partition has zero rows. Each sheet has Japanese headers, frozen row 1, auto-filter, adjusted widths, text formats for phones/postal codes, and hyperlinks for official/source URLs. Display text is limited to Excel's cell limit. Strings beginning with `=`, `+`, `-`, or `@` receive an apostrophe to prevent formula injection.

## Column definition

Columns cover IDs; legal/store/display names; searched and inferred industries; primary/mobile/fixed/all phones and uses; postal/address components; official/source URLs; search geography, word, query, provider, and rank; official/business scores and decisions; review, exclusion/positive/negative reasons; HTTP and processing states; and fetched/last-checked timestamps.

## Safe replacement

ExportRepository reads one SQLite snapshot; Excel never rereads CSV. ExportService generates every file under a unique temporary name before replacing outputs. Existing outputs are moved to temporary backups during replacement. Generation or replacement failure removes temporary/new files and restores backups, preserving the last known-good outputs.

## Status aggregation

StatusService returns a display model rather than printing. It aggregates condition totals by state, business and official counts, mobile and no-phone counts, review/exclusion/retry/error counts, today's and cumulative pages, current URLs, and the earliest retry time from SQLite.

## CLI exit codes

- `python -m src.cli status`: format the StatusService model.
- `python -m src.cli export`: regenerate CSV and Excel from SQLite.
- Success: `0`; invalid command/arguments: `2`; internal database/export error: `1`.

No collection start, setup/run batch, schedule, or parallel worker is included.

## Phase 7 limit correction

`SearchCondition.max_results` now means adopted `is_business_target=True` count. `pipeline.yaml` separately caps targets and processed candidates and controls whether a no-phone target consumes the target limit. PipelineSummary exposes candidate, processed, target, official, excluded, no-phone, retry, failed, and robots-denied counters while retaining legacy aliases.

## Next-phase review

1. Validate Japanese headers and category definitions with sales operators.
2. Decide whether CSV should additionally use Excel-oriented quoting for phone columns.
3. Review backup/replace behavior on Windows file locks.
4. Define retention and privacy policy for raw pages and exported personal contact data.
5. Review collection CLI and Windows batch UX before implementation.
