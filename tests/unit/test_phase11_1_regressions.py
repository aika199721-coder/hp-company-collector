"""Offline regressions reproduced from the first bounded live-validation run."""

import json
from pathlib import Path

from bs4 import BeautifulSoup

from crawler.encoding import detect_html_encoding
from extractor.address import AddressExtractor
from extractor.industry import IndustryExtractor
from live.audit import HttpAuditRepository
from live.config import LiveValidationConfig
from live.safety import LiveSafetyFetcher
from search.providers.base import SearchResult
from search.query_builder import QueryBuilder, SearchCriteria
from search.relevance import SearchResultClassifier
from storage.sqlite import Database
from tests.unit.test_live_safety import FakeFetcher, _result

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"
ROOT = Path(__file__).resolve().parents[2]
BEAUTY_TERMS = {
    "美容室": ("美容室", "美容院", "ヘアサロン", "hair salon", "salon", "美容", "理美容")
}


def test_beauty_queries_center_on_city_and_synonyms() -> None:
    builder = QueryBuilder(BEAUTY_TERMS)

    queries = builder.build_many(SearchCriteria("沖縄県", "那覇市", "美容室"))

    assert queries[0] == "那覇市 美容室"
    assert "那覇市 美容院" in queries
    assert "那覇 ヘアサロン" in queries
    assert "那覇市 美容室 公式" in queries
    assert "site:.jp 那覇市 美容室" in queries
    assert all("沖縄県" not in query for query in queries)


def test_search_relevance_rejects_public_tourism_and_keeps_salon() -> None:
    values = json.loads((SAMPLES / "phase11_1_search_results.json").read_text(encoding="utf-8"))
    classifier = SearchResultClassifier(BEAUTY_TERMS)
    decisions = [
        classifier.classify(
            SearchResult(item["title"], item["url"], item["snippet"], "fake", 1), "美容室"
        )
        for item in values
    ]

    assert [decision.accepted for decision in decisions] == [False, False, True]
    assert decisions[0].reason == "prefetch_government"
    assert decisions[1].reason == "prefetch_tourism"


def test_japanese_encoding_detection_without_trusting_implicit_latin1() -> None:
    plain = (SAMPLES / "encoding_no_charset.html").read_bytes()
    meta_utf8 = (SAMPLES / "encoding_meta_utf8.html").read_bytes()
    shift_source = (SAMPLES / "encoding_meta_shiftjis.html").read_text(encoding="utf-8")
    shift_bytes = shift_source.encode("shift_jis")

    assert detect_html_encoding(plain, {"content-type": "text/html"}, "ISO-8859-1") == "utf-8"
    assert detect_html_encoding(meta_utf8, {"content-type": "text/html"}) == "utf-8"
    assert detect_html_encoding(shift_bytes, {"content-type": "text/html"}) == "shift_jis"
    assert "美容室" in shift_bytes.decode(detect_html_encoding(shift_bytes, {}))


def test_normal_page_script_does_not_trigger_captcha(tmp_path: Path) -> None:
    html = (SAMPLES / "captcha_normal_page.html").read_bytes()
    database = Database(tmp_path / "audit.sqlite3")
    database.initialize()
    config = LiveValidationConfig.load(ROOT / "config/live_validation.yaml")
    safety = LiveSafetyFetcher(
        FakeFetcher([_result(content=html)]),
        config,
        HttpAuditRepository(database),
        "run-normal",
    )

    assert safety.fetch("https://travel.example/article").error is None


def test_narrative_address_and_tourism_industry_are_not_extracted() -> None:
    address_html = (SAMPLES / "narrative_address.html").read_text(encoding="utf-8")
    tourism_html = (SAMPLES / "tourism_restaurant_mention.html").read_text(encoding="utf-8")

    assert AddressExtractor().extract(BeautifulSoup(address_html, "html.parser")) is None
    assert IndustryExtractor().extract(BeautifulSoup(tourism_html, "html.parser")) is None
