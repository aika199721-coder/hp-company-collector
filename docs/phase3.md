# Phase 3 — Search foundation

## Scope

Phase 3 implements the search foundation only, in this reviewed order:

1. `QueryBuilder`
2. `SearchProvider` abstract contract and normalized `SearchResult`
3. `BingRSSProvider`
4. `SearchManager`

Yahoo, DuckDuckGo, Mojeek, Bing HTML, and all company-site crawling are explicitly out of scope.

## Design

- `QueryBuilder` validates prefecture, municipality, and industry, then produces a deterministic phrase query.
- `SearchProvider` makes providers replaceable without exposing provider response formats to callers.
- `BingRSSProvider` accepts an injectable minimal HTTP client. Production may use `requests.Session`, while tests cannot accidentally require the network.
- RSS parsing yields immutable normalized results and ignores incomplete items. Malformed XML and request failures become `SearchProviderError`.
- `SearchManager` runs providers in configured order, enforces a global result limit, ignores unsafe/non-HTTP URLs, de-duplicates normalized URLs, and isolates expected provider failures.

## Test policy

Tests use only synthetic files under `tests/html_samples` and fake providers/HTTP clients. They must not contact Bing or any other live site. Query construction, the abstract contract, RSS parsing/errors, orchestration, de-duplication, limits, and provider failure isolation have separate pytest coverage.

## Review checklist

1. Confirm the Japanese query shape before introducing query variants.
2. Confirm whether URL de-duplication should later discard known tracking query parameters.
3. Confirm Bing RSS terms of operation and operational rate limits before enabling an end-user command.
4. Review and improve Phase 3 before adding another provider or any crawler behavior.
