"""Phase 6 Step 1 DomainClassifier tests."""

from pathlib import Path

from scoring.domain import DomainClassifier


def test_matches_excluded_domain_and_subdomains(tmp_path: Path) -> None:
    excluded = tmp_path / "exclude_domains.txt"
    excluded.write_text("portal.example\njobs.example\n", encoding="utf-8")
    classifier = DomainClassifier(excluded)

    assert classifier.classify("https://portal.example/list").is_excluded is True
    result = classifier.classify("https://shop.portal.example/store")
    assert result.is_excluded is True
    assert result.matched_domain == "portal.example"


def test_allows_unlisted_chain_and_free_host_subdomains(tmp_path: Path) -> None:
    excluded = tmp_path / "exclude_domains.txt"
    excluded.write_text("portal.example\n", encoding="utf-8")
    classifier = DomainClassifier(excluded)

    assert classifier.classify("https://tokyo.chain.example/").is_excluded is False
    assert classifier.classify("https://shop.free-homepage.example/").is_excluded is False


def test_excludes_government_and_association_suffixes(tmp_path: Path) -> None:
    """Classify reserved organization suffixes without listing every host."""
    excluded = tmp_path / "exclude_domains.txt"
    excluded.write_text("portal.example\n", encoding="utf-8")
    classifier = DomainClassifier(excluded)

    assert classifier.classify("https://city.example.lg.jp/").category == "government"
    assert classifier.classify("https://trade.example.or.jp/").category == "association"
