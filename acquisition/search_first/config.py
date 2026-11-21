"""Configuration models for general-purpose search-first acquisition."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SearchTarget:
    name: str
    url: str
    state: str | None = None
    county: str | None = None


@dataclass
class SearchConfig:
    name: str
    objective: str
    country: str = "US"
    targets: list[SearchTarget] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)
    provider: str = "serpapi"
