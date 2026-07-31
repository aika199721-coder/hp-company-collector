"""Offline robots.txt parser tests."""

from pathlib import Path

import pytest

from crawler.robots import RobotsPolicy

SAMPLES = Path(__file__).resolve().parents[1] / "html_samples"


def test_parses_allow_disallow_and_crawl_delay_from_fixture() -> None:
    content = (SAMPLES / "robots.txt").read_text(encoding="utf-8")
    policy = RobotsPolicy.parse("https://company.example.jp/about", content, "hp-company-collector")

    assert policy.robots_url == "https://company.example.jp/robots.txt"
    assert policy.can_fetch("https://company.example.jp/about") is True
    assert policy.can_fetch("https://company.example.jp/private/secret") is False
    assert policy.can_fetch("https://company.example.jp/private/public.html") is True
    assert policy.can_fetch("https://other.example.jp/about") is False
    assert policy.crawl_delay == 3.0


def test_empty_user_agent_is_rejected() -> None:
    with pytest.raises(ValueError, match="user_agent"):
        RobotsPolicy.parse("https://example.jp", "User-agent: *", " ")
