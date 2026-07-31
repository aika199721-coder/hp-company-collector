"""Phase 6 Step 2 PageTypeClassifier tests with HTML fixtures."""

from pathlib import Path

import pytest

from scoring.page_type import PageTypeClassifier

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


@pytest.mark.parametrize(
    ("fixture", "url", "expected"),
    [
        ("scoring_official.html", "https://sakura.example/", "official_home"),
        ("scoring_official.html", "https://sakura.example/company", "company"),
        ("scoring_store.html", "https://shop.example/stores/shinjuku", "store"),
        ("scoring_portal.html", "https://portal.example/ranking", "portal"),
        ("scoring_official.html", "https://sakura.example/contact", "contact"),
        ("scoring_official.html", "https://sakura.example/access", "access"),
        ("scoring_official.html", "https://sakura.example/article", "article"),
        ("scoring_official.html", "https://sakura.example/job", "job"),
    ],
)
def test_classifies_from_url_and_fixture_signals(fixture: str, url: str, expected: str) -> None:
    html = (SAMPLES / fixture).read_text(encoding="utf-8")

    assert PageTypeClassifier().classify(url, html).value == expected
