"""Central dependency composition for the executable application layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from application.config import ApplicationConfig
from application.shutdown import ShutdownController
from crawler.fetcher import Fetcher
from crawler.rate_limiter import RateLimiter
from crawler.robots import RobotsPolicy
from export.service import ExportService
from extractor.facade import ExtractorFacade
from pipeline.coordinator import PipelineCoordinator
from pipeline.models import PipelineLimits
from pipeline.processor import CandidateProcessor
from scoring.facade import ScoringFacade
from search.audit import SearchProviderAuditRepository
from search.manager import SearchManager
from search.providers.bing_html import BingHtmlProvider
from search.providers.bing_rss import BingRSSProvider
from search.providers.brave import BraveSearchProvider
from search.providers.duckduckgo import DuckDuckGoHtmlProvider
from search.providers.mojeek import MojeekProvider
from search.providers.searxng import SearXNGProvider
from search.providers.yahoo_japan import YahooJapanHtmlProvider
from search.query_builder import QueryBuilder
from search.relevance import SearchResultClassifier
from status.service import StatusService
from storage.pipeline import PipelineRepository
from storage.progress import ProgressStore
from storage.run_history import RunHistoryRepository
from storage.sqlite import Database


class CachedRobotsChecker:
    """Load each origin robots policy once and fail closed on transport errors."""

    def __init__(
        self, client: requests.Session, limiter: RateLimiter, user_agent: str, timeout: float
    ) -> None:
        self._client = client
        self._limiter = limiter
        self._user_agent = user_agent
        self._timeout = timeout
        self._policies: dict[str, RobotsPolicy | None] = {}

    def can_fetch(self, url: str) -> bool:
        """Return permission from the cached origin policy."""
        parts = urlsplit(url)
        origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        if origin not in self._policies:
            robots_url = f"{origin}/robots.txt"
            try:
                self._limiter.wait(robots_url)
                response = self._client.get(
                    robots_url,
                    timeout=self._timeout,
                    allow_redirects=True,
                    headers={"User-Agent": self._user_agent},
                )
                policy = RobotsPolicy.parse(origin, response.text, self._user_agent)
                self._policies[origin] = policy if response.status_code == 200 else None
            except requests.RequestException:
                return False
        policy = self._policies[origin]
        return True if policy is None else policy.can_fetch(url)


@dataclass(frozen=True, slots=True)
class ApplicationComponents:
    """Fully composed services exposed to application commands."""

    database: Database
    progress: ProgressStore
    repository: PipelineRepository
    query_builder: QueryBuilder
    search_manager: SearchManager
    fetcher: Any
    extractor: Any
    scorer: Any
    processor: CandidateProcessor
    coordinator: PipelineCoordinator
    export_service: ExportService
    status_service: StatusService
    run_history: RunHistoryRepository


class ApplicationFactory:
    """Create concrete dependencies once while allowing test overrides by name."""

    def __init__(
        self,
        config: ApplicationConfig,
        *,
        overrides: dict[str, Any] | None = None,
        shutdown: ShutdownController | None = None,
    ) -> None:
        self.config = config
        self._overrides = overrides or {}
        self.shutdown = shutdown or ShutdownController()

    def build(self) -> ApplicationComponents:
        """Initialize SQLite and compose all Phase 9 services."""
        database = self._get("database", Database(self.config.database_path))
        database.initialize()
        progress = self._get("progress", ProgressStore(database))
        repository = self._get("repository", PipelineRepository(database))
        synonyms = _industry_synonyms(self.config.industries)
        query_builder = self._get("query_builder", QueryBuilder(synonyms))
        result_classifier = self._get(
            "result_classifier", SearchResultClassifier(synonyms, self.config.excluded_domains)
        )
        client = self._get("http_client", requests.Session())
        providers = self._get("providers", _build_search_providers(self.config, client))
        provider_auditor = self._get(
            "provider_auditor", SearchProviderAuditRepository(database)
        )
        priorities = {
            name: int(settings["priority"])
            for name, settings in self.config.providers.items()
            if settings.get("enabled")
        }
        configured = {
            name: bool(settings.get("enabled"))
            for name, settings in self.config.providers.items()
        }
        search_manager = self._get(
            "search_manager",
            SearchManager(
                providers,
                priorities=priorities,
                auditor=provider_auditor,
                configured=configured,
            ),
        )
        search_decorator = self._overrides.get("search_manager_decorator")
        if search_decorator is not None:
            search_manager = search_decorator(search_manager)
        limiter = self._get("rate_limiter", RateLimiter(self.config.per_domain_delay_seconds))
        robots = self._get(
            "robots",
            CachedRobotsChecker(
                client,
                limiter,
                self.config.user_agent,
                self.config.request_timeout_seconds,
            ),
        )
        fetcher = self._get(
            "fetcher",
            Fetcher(
                robots,
                limiter,
                client=client,
                user_agent=self.config.user_agent,
                timeout_seconds=self.config.request_timeout_seconds,
                max_redirects=self.config.max_redirects,
            ),
        )
        decorator = self._overrides.get("fetcher_decorator")
        if decorator is not None:
            fetcher = decorator(fetcher)
        extractor = self._get("extractor", ExtractorFacade())
        scorer = self._get(
            "scorer",
            ScoringFacade(
                self.config.scoring,
                exclude_domains_path=self.config.config_file.parent / "exclude_domains.txt",
                industry_keywords_path=self.config.config_file.parent / "industry_keywords.yaml",
            ),
        )
        processor = self._get(
            "processor", CandidateProcessor(fetcher, extractor, scorer, repository, progress)
        )
        coordinator = self._get(
            "coordinator",
            PipelineCoordinator(
                query_builder,
                search_manager,
                repository,
                progress,
                processor,
                limits=self.config.pipeline_limits,
                stop_requested=self.shutdown.is_requested,
                result_classifier=result_classifier,
                max_queries=int(self._overrides.get("max_queries", 5)),
                results_per_query=int(self._overrides.get("results_per_query", 10)),
            ),
        )
        return ApplicationComponents(
            database,
            progress,
            repository,
            query_builder,
            search_manager,
            fetcher,
            extractor,
            scorer,
            processor,
            coordinator,
            self._get("export_service", ExportService(database, self.config.output_path)),
            self._get("status_service", StatusService(database)),
            self._get("run_history", RunHistoryRepository(database)),
        )

    def _get(self, name: str, default: Any) -> Any:
        return self._overrides.get(name, default)

    def coordinator_for(
        self, components: ApplicationComponents, limits: PipelineLimits
    ) -> PipelineCoordinator:
        """Create a coordinator variant for per-input-row limits."""
        if "coordinator" in self._overrides:
            return components.coordinator
        return PipelineCoordinator(
            components.query_builder,
            components.search_manager,
            components.repository,
            components.progress,
            components.processor,
            limits=limits,
            stop_requested=self.shutdown.is_requested,
            result_classifier=self._get(
                "result_classifier",
                SearchResultClassifier(
                    _industry_synonyms(self.config.industries), self.config.excluded_domains
                ),
            ),
            max_queries=int(self._overrides.get("max_queries", 5)),
            results_per_query=int(self._overrides.get("results_per_query", 10)),
        )


def _industry_synonyms(industries: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Index configurable keywords by display label and each individual synonym."""
    aliases: dict[str, tuple[str, ...]] = {}
    for settings in industries.values():
        if not isinstance(settings, dict):
            continue
        display = str(settings.get("display_name", "")).strip()
        keywords = tuple(
            str(item).strip() for item in settings.get("keywords", ()) if str(item).strip()
        )
        terms = tuple(dict.fromkeys((display, *keywords)))
        for alias in terms:
            aliases[alias] = terms
    return aliases


def _build_search_providers(config: ApplicationConfig, client: Any) -> list[Any]:
    """Build enabled free providers in configured priority order."""
    factories = {
        "bing_rss": lambda settings: BingRSSProvider(client, config.request_timeout_seconds),
        "bing_html": lambda settings: BingHtmlProvider(client, config.request_timeout_seconds),
        "yahoo_japan_html": lambda settings: YahooJapanHtmlProvider(
            client, config.request_timeout_seconds
        ),
        "duckduckgo_html": lambda settings: DuckDuckGoHtmlProvider(
            client, config.request_timeout_seconds
        ),
        "brave_search": lambda settings: BraveSearchProvider(
            client, config.request_timeout_seconds
        ),
        "mojeek": lambda settings: MojeekProvider(client, config.request_timeout_seconds),
        "searxng": lambda settings: SearXNGProvider(
            str(settings.get("base_url", "")), client, config.request_timeout_seconds
        ),
    }
    enabled = sorted(
        (
            (name, settings)
            for name, settings in config.providers.items()
            if settings.get("enabled")
        ),
        key=lambda item: int(item[1]["priority"]),
    )
    providers: list[Any] = []
    for name, settings in enabled:
        factory = factories.get(name)
        if factory is None:
            raise ValueError(f"Unsupported enabled search provider: {name}")
        providers.append(factory(settings))
    return providers
