# Phase 5 — Extraction engine

## Scope and implementation order

Phase 5 implements only extraction from supplied HTML, in the requested order:

1. JSON-LD parser
2. schema.org microdata parser
3. `CompanyNameExtractor`
4. `AddressExtractor`
5. `PhoneExtractor`
6. `IndustryExtractor`
7. `ExtractorFacade`

The engine performs no HTTP or Playwright access. Tests use synthetic HTML fixtures only.

## Structured data

JSON-LD and schema.org accept `Organization`, `LocalBusiness`, `HairSalon`, `MedicalBusiness`, and `Restaurant`. Malformed and unrelated JSON-LD blocks are ignored. Extracted structured entities retain their recognized types and properties.

## Priority and normalization

- Company name: JSON-LD → schema.org → footer → copyright → company profile → OGP → title → h1.
- Address: JSON-LD → company profile → access → footer → document body.
- Phone: FAX-labelled numbers are excluded; 070, 080, and 090 numbers are classified as mobile and ordered before fixed numbers. Nearby labels estimate reservation, recruiting, contact, emergency, main, or unknown use.
- Industry: JSON-LD type → schema.org type → visible keyword evidence.
- Every final value includes provenance such as `jsonld`, `schema`, `company`, or `body`.

## Offline tests

Separate pytest modules cover every step. Fixtures exercise all supported JSON-LD types, nested schema.org addresses, every company-name fallback, address priority, FAX exclusion, mobile priority, use estimation, industry mapping, malformed JSON-LD, and facade coordination.

## Review checklist

1. Review legal-name boundaries against additional synthetic Japanese company-name fixtures.
2. Decide whether toll-free and IP-phone formatting should be expanded in a focused improvement.
3. Review Japanese address coverage for wards, counties, towns, buildings, and Kyoto street notation.
4. Review and improve Phase 5 before implementing official-site or business scoring.
