"""Configurable pre-fetch relevance and hard-exclusion classification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from urllib.parse import urlsplit

from search.providers.base import SearchResult

_HARD_DOMAIN_FRAGMENTS = ("wikipedia.org", ".go.jp")
_HARD_TEXT_SIGNALS = {
    "government": ("県公式", "市役所", "自治体", "pref.okinawa", "city."),
    "news": ("ニュース", "新聞", "沖縄タイムス", "news"),
    "tourism": ("観光", "旅行", "トラベル", "tour", "travel"),
    "article": ("ランキング", "まとめ", "おすすめ記事", "特集"),
}


@dataclass(frozen=True, slots=True)
class RelevanceDecision:
    """Pre-fetch decision with a durable operator-facing reason."""

    accepted: bool
    reason: str | None = None


class SearchResultClassifier:
    """Reject obvious non-business and keyword-free results before HTTP fetching."""

    def __init__(
        self,
        industry_synonyms: Mapping[str, Sequence[str]],
        excluded_domains: Sequence[str] = (),
    ) -> None:
        self._synonyms = {
            key: tuple(item.lower() for item in values if item.strip())
            for key, values in industry_synonyms.items()
        }
        self._excluded = tuple(domain.lower().lstrip(".") for domain in excluded_domains)

    def classify(self, result: SearchResult, industry: str) -> RelevanceDecision:
        """Classify using URL, title, and snippet only; never fetch a rejected URL."""
        host = (urlsplit(result.url).hostname or "").lower().rstrip(".")
        text = " ".join((result.title, result.snippet, result.url)).lower()
        if any(host == item or host.endswith(f".{item}") for item in self._excluded):
            return RelevanceDecision(False, "prefetch_excluded_domain")
        if any(fragment in host for fragment in _HARD_DOMAIN_FRAGMENTS):
            return RelevanceDecision(False, "prefetch_public_or_wikipedia")
        for category, signals in _HARD_TEXT_SIGNALS.items():
            if any(signal.lower() in text for signal in signals):
                return RelevanceDecision(False, f"prefetch_{category}")
        if not any(term in text for term in self._terms(industry)):
            return RelevanceDecision(False, "prefetch_low_industry_relevance")
        return RelevanceDecision(True)

    def _terms(self, industry: str) -> tuple[str, ...]:
        direct = self._synonyms.get(industry)
        if direct:
            return tuple(dict.fromkeys((industry.lower(), *direct)))
        matching = next(
            (
                values
                for key, values in self._synonyms.items()
                if industry in key or key in industry or any(industry in value for value in values)
            ),
            (),
        )
        return tuple(dict.fromkeys((industry.lower(), *matching)))
