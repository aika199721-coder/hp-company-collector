"""Phase 1 のプロジェクト構成を保護するテスト。"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_required_directories_exist() -> None:
    """設計で合意した責務別ディレクトリが存在することを確認する。"""
    required = {
        "config",
        "data",
        "docs",
        "input",
        "logs",
        "output",
        "src/search",
        "src/search/providers",
        "src/crawler",
        "src/extractor",
        "src/scoring",
        "src/storage",
        "src/export",
        "src/utils",
        "tests/html_samples",
        "tests/integration",
        "tests/unit",
    }

    missing = sorted(path for path in required if not (ROOT / path).is_dir())
    assert not missing, f"Missing required directories: {missing}"


def test_phase3_documentation_and_fixture_exist() -> None:
    """Phase 3 documentation and offline RSS fixture are tracked."""
    assert (ROOT / "docs/phase3.md").is_file()
    assert (ROOT / "tests/html_samples/bing_rss.xml").is_file()


def test_phase4_documentation_and_offline_fixtures_exist() -> None:
    """Phase 4 documentation and crawler fixtures are tracked."""
    assert (ROOT / "docs/phase4.md").is_file()
    assert (ROOT / "tests/html_samples/robots.txt").is_file()


def test_phase5_documentation_and_extractor_fixture_exist() -> None:
    """Phase 5 documentation and extraction fixture are tracked."""
    assert (ROOT / "docs/phase5.md").is_file()
    assert (ROOT / "tests/html_samples/extractor_full.html").is_file()


def test_phase6_configuration_documentation_and_fixture_exist() -> None:
    """Phase 6 configuration, documentation, and scoring fixture are tracked."""
    assert (ROOT / "config/scoring.yaml").is_file()
    assert (ROOT / "docs/phase6.md").is_file()
    assert (ROOT / "tests/html_samples/scoring_official.html").is_file()


def test_phase7_pipeline_documentation_and_package_exist() -> None:
    """Phase 7 pipeline package and design documentation are tracked."""
    assert (ROOT / "src/pipeline/coordinator.py").is_file()
    assert (ROOT / "docs/phase7.md").is_file()


def test_phase8_export_status_cli_and_documentation_exist() -> None:
    """Phase 8 packages, CLI, configuration, and documentation are tracked."""
    assert (ROOT / "config/pipeline.yaml").is_file()
    assert (ROOT / "docs/phase8.md").is_file()
    assert (ROOT / "src/export/service.py").is_file()
    assert (ROOT / "src/status/service.py").is_file()
    assert (ROOT / "src/cli.py").is_file()


def test_crawler_defaults_are_safe() -> None:
    """robots.txt の遵守とドメイン待機が安全な既定値であることを確認する。"""
    config = yaml.safe_load((ROOT / "config/default.yaml").read_text(encoding="utf-8"))

    assert config["crawler"]["respect_robots_txt"] is True
    assert config["crawler"]["per_domain_delay_seconds"] > 0
    assert config["crawler"]["resume_enabled"] is True


def test_runtime_dependencies_do_not_contain_prohibited_services() -> None:
    """Phase 1 の依存一覧に禁止された有料・Google API SDK がないことを確認する。"""
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    prohibited = ("googlemaps", "google-cloud", "google-api-python-client")

    assert not any(package in requirements for package in prohibited)
