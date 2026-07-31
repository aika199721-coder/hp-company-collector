# Phase 4 — Crawler foundation

## Scope and implementation order

Phase 4 implements only the transport layer, in the requested order:

1. `RobotsPolicy` parser
2. per-origin `RateLimiter`
3. injectable requests-compatible `Fetcher`
4. immutable `FetchResult`
5. injectable `PlaywrightFallback`

HTML parsing, company names, phone numbers, addresses, and all other company-information extraction are explicitly out of scope.

## Behavior

- robots.txt selects the most specific user-agent group and applies longest-rule matching with Allow winning equal-length ties.
- Rate limiting uses an injectable monotonic clock and sleeper, with independent schedules per HTTP(S) origin.
- Fetcher checks robots and rate limits before every request. Redirects are followed manually so each target is checked before access.
- HTTP 429 and 404 are returned without retry or browser fallback. A 403 may use the injected Playwright fallback.
- Timeouts and expected request failures become transport errors in `FetchResult` rather than extraction behavior.
- gzip bytes are decompressed when necessary; response/header encodings are recorded and decoding uses replacement for invalid bytes.
- FetchResult contains raw bytes, headers, status, redirects, encoding, and source metadata only.

## Offline test policy

Tests use only synthetic fixtures under `tests/html_samples`, fake requests-compatible clients, fake clocks/sleepers, and fake Playwright pages. No test accesses a live website. Coverage includes robots rules, 429, 403, 404, timeout, redirect and redirect denial, gzip, encoding, rate limiting, FetchResult, and Playwright navigation.

## Review checklist

1. Confirm whether 429 retry policy belongs in a later orchestration layer.
2. Confirm whether Playwright should be enabled by default or explicitly opted in per run.
3. Define robots.txt download/cache behavior before a runnable crawl command is added.
4. Review and improve Phase 4 before beginning any HTML or company-information extraction.
