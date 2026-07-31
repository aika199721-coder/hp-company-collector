"""Page-type classification from URL and visible document signals."""

from __future__ import annotations

import re
from enum import StrEnum
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag


class PageType(StrEnum):
    """Supported page classifications."""

    OFFICIAL_HOME = "official_home"
    COMPANY = "company"
    STORE = "store"
    CONTACT = "contact"
    ACCESS = "access"
    ARTICLE = "article"
    JOB = "job"
    PORTAL = "portal"
    DIRECTORY = "directory"
    UNKNOWN = "unknown"


class PageTypeClassifier:
    """Classify a page using URL, title, description, h1, and body keywords."""

    def classify(self, url: str, html: str) -> PageType:
        """Return the highest-confidence supported page type."""
        soup = BeautifulSoup(html, "html.parser")
        path = urlsplit(url).path.lower()
        title = _text(soup.title)
        h1 = _text(soup.find("h1"))
        description_node = soup.find("meta", attrs={"name": re.compile("description", re.I)})
        description = (
            str(description_node.get("content", ""))
            if isinstance(description_node, Tag)
            else ""
        )
        body = soup.get_text(" ", strip=True)
        evidence = " ".join((path, title, description, h1, body[:3000])).lower()

        harmful_rules = (
            (PageType.PORTAL, r"ポータル|ランキング|まとめ|おすすめ.*一覧|比較サイト"),
            (PageType.JOB, r"求人|採用情報|recruit|/jobs?"),
            (PageType.DIRECTORY, r"電話帳|企業一覧|店舗一覧|directory"),
            (PageType.ARTICLE, r"/articles?|/blog|ニュース|コラム|記事"),
        )
        for page_type, pattern in harmful_rules:
            if re.search(pattern, evidence, re.IGNORECASE):
                return page_type
        path_rules = (
            (PageType.CONTACT, r"/contact(?:/|$)"),
            (PageType.ACCESS, r"/access(?:/|$)"),
            (PageType.COMPANY, r"/(?:company|about)(?:/|$)"),
            (PageType.STORE, r"/(?:stores?|shop)(?:/|$)"),
        )
        for page_type, pattern in path_rules:
            if re.search(pattern, path, re.IGNORECASE):
                return page_type
        if path in {"", "/", "/index.html", "/index.htm"}:
            return PageType.OFFICIAL_HOME
        primary = " ".join((title, description, h1))
        content_rules = (
            (PageType.CONTACT, r"お問い合わせ|問合せ"),
            (PageType.ACCESS, r"アクセス|交通案内"),
            (PageType.COMPANY, r"会社概要|法人概要"),
            (PageType.STORE, r"店舗情報|\w+店"),
        )
        for page_type, pattern in content_rules:
            if re.search(pattern, primary, re.IGNORECASE):
                return page_type
        return PageType.UNKNOWN


def _text(node: object) -> str:
    return node.get_text(" ", strip=True) if isinstance(node, Tag) else ""
