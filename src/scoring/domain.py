"""Domain exclusion classification with exact and subdomain matching."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

_CATEGORY_HINTS = {
    "job": ("job", "jobs", "recruit", "求人"),
    "news": ("news",),
    "blog": ("blog",),
    "map": ("map", "maps"),
    "social": ("facebook", "instagram", "youtube", "x.com"),
    "directory": ("itp", "townpage", "directory"),
    "portal": ("portal", "ranking", "matome"),
    "marketplace": ("rakuten", "amazon", "yahoo"),
    "reservation": ("reserve", "booking", "hotpepper"),
    "government": ("go.jp", "lg.jp"),
    "association": ("association", "or.jp"),
}
_EXCLUDED_SUFFIXES = {"go.jp": "government", "lg.jp": "government", "or.jp": "association"}


@dataclass(frozen=True, slots=True)
class DomainClassification:
    """Domain exclusion decision with an auditable match and category."""

    hostname: str
    is_excluded: bool
    category: str | None
    matched_domain: str | None
    reason: str | None


class DomainClassifier:
    """Classify configured excluded domains without excluding unknown subdomains."""

    def __init__(self, exclude_domains_path: Path) -> None:
        try:
            lines = Path(exclude_domains_path).read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise ValueError(f"Unable to read excluded domains: {exclude_domains_path}") from exc
        self._excluded = tuple(
            line.strip().lower().rstrip(".")
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        )

    def classify(self, url: str) -> DomainClassification:
        """Match a hostname exactly or as a subdomain of a configured entry."""
        hostname = (urlsplit(url).hostname or "").lower().rstrip(".")
        if not hostname:
            raise ValueError("url must contain a hostname")
        matched = next(
            (
                domain
                for domain in self._excluded
                if hostname == domain or hostname.endswith(f".{domain}")
            ),
            None,
        )
        suffix_match = next(
            (
                (suffix, category)
                for suffix, category in _EXCLUDED_SUFFIXES.items()
                if hostname == suffix or hostname.endswith(f".{suffix}")
            ),
            None,
        )
        if matched is None and suffix_match is not None:
            suffix, category = suffix_match
            return DomainClassification(
                hostname,
                True,
                category,
                suffix,
                f"除外ドメイン種別に一致: {suffix} ({category})",
            )
        if matched is None:
            return DomainClassification(hostname, False, None, None, None)
        category = _category(matched)
        return DomainClassification(
            hostname,
            True,
            category,
            matched,
            f"除外ドメインに一致: {matched} ({category})",
        )


def _category(domain: str) -> str:
    return next(
        (
            category
            for category, hints in _CATEGORY_HINTS.items()
            if any(hint in domain for hint in hints)
        ),
        "excluded",
    )
