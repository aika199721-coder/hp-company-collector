"""robots.txt parsing and access decisions without network I/O."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit


@dataclass(frozen=True, slots=True)
class _Rule:
    allow: bool
    pattern: str

    def matches(self, path: str) -> bool:
        expression = re.escape(self.pattern).replace(r"\*", ".*")
        if expression.endswith(r"\$"):
            expression = expression[:-2] + "$"
        return re.match(expression, path) is not None

    @property
    def specificity(self) -> int:
        return len(self.pattern.replace("*", "").removesuffix("$"))


@dataclass(frozen=True, slots=True)
class _Group:
    agents: tuple[str, ...]
    rules: tuple[_Rule, ...]
    delay: float | None


@dataclass(frozen=True, slots=True)
class RobotsPolicy:
    """Parsed robots.txt rules scoped to one site and user agent."""

    robots_url: str
    user_agent: str
    _origin: str
    _rules: tuple[_Rule, ...]
    _crawl_delay: float | None

    @classmethod
    def parse(cls, site_url: str, content: str, user_agent: str) -> RobotsPolicy:
        """Parse fixture or downloaded robots.txt text for a site."""
        if not user_agent.strip():
            raise ValueError("user_agent must not be empty")
        groups = _parse_groups(content)
        selected = _select_groups(groups, user_agent)
        rules = tuple(rule for group in selected for rule in group.rules)
        delay = next((group.delay for group in selected if group.delay is not None), None)
        robots_url = urljoin(site_url, "/robots.txt")
        return cls(robots_url, user_agent, _url_origin(robots_url), rules, delay)

    def can_fetch(self, url: str) -> bool:
        """Return whether the configured crawler may fetch an absolute URL."""
        parts = urlsplit(url)
        if _url_origin(url) != self._origin:
            return False
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        matches = [rule for rule in self._rules if rule.matches(path)]
        if not matches:
            return True
        # RFC 9309: longest match wins, and Allow wins equal-length ties.
        winner = max(matches, key=lambda rule: (rule.specificity, rule.allow))
        return winner.allow

    @property
    def crawl_delay(self) -> float | None:
        """Return a positive crawler-specific delay when provided."""
        return self._crawl_delay


def _parse_groups(content: str) -> tuple[_Group, ...]:
    groups: list[_Group] = []
    agents: list[str] = []
    rules: list[_Rule] = []
    delay: float | None = None
    has_directives = False

    def finish() -> None:
        nonlocal agents, rules, delay, has_directives
        if agents:
            groups.append(_Group(tuple(agents), tuple(rules), delay))
        agents, rules, delay, has_directives = [], [], None, False

    for raw_line in content.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = (part.strip() for part in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if has_directives:
                finish()
            agents.append(value.lower())
        elif agents and field in {"allow", "disallow"}:
            has_directives = True
            if value:  # An empty Disallow/Allow has no matching rule.
                rules.append(_Rule(field == "allow", value))
        elif agents and field == "crawl-delay":
            has_directives = True
            try:
                parsed = float(value)
            except ValueError:
                continue
            if parsed > 0:
                delay = parsed
    finish()
    return tuple(groups)


def _select_groups(groups: tuple[_Group, ...], user_agent: str) -> tuple[_Group, ...]:
    product = user_agent.lower().split("/", 1)[0]
    specific = [
        group
        for group in groups
        if any(agent != "*" and agent in product for agent in group.agents)
    ]
    if specific:
        best = max(
            len(agent)
            for group in specific
            for agent in group.agents
            if agent != "*" and agent in product
        )
        return tuple(
            group
            for group in specific
            if any(
                agent != "*" and agent in product and len(agent) == best
                for agent in group.agents
            )
        )
    return tuple(group for group in groups if "*" in group.agents)


def _url_origin(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("url must be an absolute HTTP(S) URL")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("url must be an absolute HTTP(S) URL") from exc
    default_port = (parts.scheme.lower() == "http" and port == 80) or (
        parts.scheme.lower() == "https" and port == 443
    )
    authority = (
        parts.hostname.lower()
        if port is None or default_port
        else f"{parts.hostname}:{port}"
    )
    return f"{parts.scheme.lower()}://{authority}"
