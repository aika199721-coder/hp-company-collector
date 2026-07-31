"""Configurable official-site scoring with auditable signal reasons."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from extractor.facade import ExtractionResult
from extractor.jsonld import JsonLdParser
from scoring.models import ScoreBreakdown, SearchContext
from scoring.page_type import PageType


class OfficialSiteScorer:
    """Score official-site evidence from extraction, page, and search context."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        try:
            self._weights = config["weights"]["official"]
            self._limits = config["limits"]
        except (KeyError, TypeError) as exc:
            raise ValueError("official scoring configuration is incomplete") from exc

    def score(
        self,
        extraction: ExtractionResult,
        url: str,
        html: str,
        context: SearchContext,
        page_type: PageType,
        *,
        domain_excluded: bool,
    ) -> ScoreBreakdown:
        """Return a bounded score and all positive/negative evidence."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        positives: list[str] = []
        negatives: list[str] = []
        reasons: list[str] = []
        score = 0.0

        def add(signal: str, reason: str) -> None:
            nonlocal score
            score += float(self._weights[signal])
            positives.append(signal)
            reasons.append(reason)

        def subtract(signal: str, reason: str) -> None:
            nonlocal score
            score += float(self._weights[signal])
            negatives.append(signal)
            reasons.append(reason)

        if extraction.phones:
            add("phone", "電話番号を確認")
        if extraction.address:
            add("address", "住所を確認")
        names = (extraction.company_name, extraction.store_name, extraction.display_name)
        if any(names):
            add("identity", "法人名または店舗名を確認")
        structured_types = {
            item for entity in JsonLdParser().parse(soup) for item in entity.types
        }
        business_types = {
            "Organization",
            "LocalBusiness",
            "HairSalon",
            "MedicalBusiness",
            "Restaurant",
        }
        if structured_types.intersection(business_types):
            add("structured_business", "事業者の構造化データを確認")
        lowered = text.lower()
        if re.search(r"会社概要|法人概要|運営会社|販売業者", text):
            add("company_page", "会社概要情報を確認")
        if re.search(r"お問い合わせ|問合せ|contact", lowered, re.IGNORECASE):
            add("contact_page", "お問い合わせ導線を確認")
        if re.search(r"アクセス|交通案内|access", lowered, re.IGNORECASE):
            add("access_page", "アクセス情報を確認")

        industry_terms = (context.industry, *context.industry_keywords)
        if any(term and term in text for term in industry_terms):
            add("industry_match", "検索業種とページ内容が一致")
        elif extraction.industry and extraction.industry.value != context.industry:
            subtract("industry_mismatch", "検索業種と抽出業種が不一致")

        region_terms = (context.prefecture, context.municipality)
        if all(term and term in text for term in region_terms):
            add("region_match", "検索地域とページ内容が一致")
        elif extraction.address and extraction.address.prefecture != context.prefecture:
            subtract("region_mismatch", "検索地域と抽出住所が不一致")

        if not domain_excluded and urlsplit(url).hostname:
            add("own_domain", "除外対象でないサイトドメイン")
        company = extraction.company_name.value if extraction.company_name else None
        copyright_text = " ".join(
            node.get_text(" ", strip=True) for node in soup.find_all(["footer", "small"])
        )
        if company and company in copyright_text:
            add("copyright_match", "copyrightと法人名が一致")

        page_penalties = {
            PageType.JOB: ("job", "求人ページの特徴"),
            PageType.ARTICLE: ("article", "記事ページの特徴"),
            PageType.PORTAL: ("portal", "ポータルページの特徴"),
            PageType.DIRECTORY: ("portal", "電話帳・一覧ページの特徴"),
        }
        if page_type in page_penalties:
            signal, reason = page_penalties[page_type]
            subtract(signal, reason)
        if re.search(r"ランキング|まとめ|おすすめ\s*\d+選", text):
            subtract("ranking", "ランキング・まとめ表現を確認")
        company_count = len(set(re.findall(r"株式会社[\w一-龯ぁ-んァ-ヶー]{1,30}", text)))
        if company_count >= int(self._limits["multiple_companies"]):
            subtract("multiple_companies", "複数企業の一覧掲載を確認")
        external_hosts = _external_hosts(soup, url)
        if len(external_hosts) >= int(self._limits["many_external_links"]):
            subtract("many_external_links", "外部サイトへのリンクが大量")
        return ScoreBreakdown(_bounded(score), tuple(positives), tuple(negatives), tuple(reasons))


def _external_hosts(soup: BeautifulSoup, url: str) -> set[str]:
    own_host = urlsplit(url).hostname
    hosts: set[str] = set()
    for node in soup.select("a[href]"):
        href = node.get("href")
        host = urlsplit(str(href)).hostname if href else None
        if host and host != own_host:
            hosts.add(host)
    return hosts


def _bounded(value: float) -> int:
    return max(0, min(100, round(value)))
