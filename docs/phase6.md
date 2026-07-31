# Phase 6 — Official-site and business-target scoring

## Scope

Phase 6 implements only classification and scoring over an `ExtractionResult`, URL, search context, and already-fetched HTML. Search, Crawler, SQLite, and Export responsibilities are unchanged. Tests use synthetic HTML and fake data without live access.

## Scoring criteria

All thresholds, weights, link/company limits, and hard-excluded page types live in `config/scoring.yaml`.

Official-site positive signals include phone, address, legal/store/display identity, business JSON-LD, company/contact/access information, industry and region matches, a non-excluded domain, and matching copyright. Negative signals include job/article/portal/directory page types, rankings, multiple listed companies, many external domains, and industry or region mismatches. Scores are clamped to 0–100.

Business-target scoring starts from a configurable fraction of the official score, then considers phone/mobile availability, address, identity, and official/company/store page type. Configured excluded domains and portal, job, article, or directory pages are hard exclusions even when phone numbers exist.

Default decisions are:

- `is_official`: official score ≥ 60 and domain is not excluded.
- `is_business_target`: official and business score ≥ 55 with no hard exclusion.
- `review_required`: a non-excluded result within 8 points of either threshold.

## Reasons and safeguards

Every result retains `reasons`, `positive_signals`, and `negative_signals`; threshold failures and hard exclusions are recorded rather than silently discarded. Exact and subdomain matches from `exclude_domains.txt` are supported. Government and association suffixes are also classified.

Store subdomains, chain store pages, and unlisted free-homepage subdomains are allowed. A non-independent domain alone never causes exclusion. Portal, job, news/article, blog, ranking/summary, government, association, map/directory, social, marketplace, and reservation domains or pages can be excluded only through configured domain or classified page evidence. CAPTCHA bypass and network access are absent.

Industry bonus terms come from `industry_keywords.yaml` when the caller does not supply explicit terms.

## Misclassification controls

- Page classification prioritizes portal/job/article/directory evidence, then explicit URL paths, then primary title/description/h1 evidence; navigation link text does not turn a home page into a contact page.
- Domain exclusion does not infer that every unknown subdomain is a portal.
- Official and business decisions are separate so a plausible official page can still require review.
- Hard exclusions override phone/address positives, preventing directory and job pages from becoming targets.
- Legal company, store, and display names remain separate to avoid treating a brand as the corporation.

## Next-phase review

1. Review all default weights and thresholds against a labeled offline evaluation set.
2. Expand category domain lists only after legal and operational review.
3. Decide how manual review decisions will be persisted without losing original reasons.
4. Confirm export columns for scores, signals, reasons, and separate identity fields before Phase 7.
