"""Search-mode configuration for progressive website discovery."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchMode:
    name: str
    defer_low_priority: bool
    explore_remaining: bool


SURFACE = SearchMode(
    name="surface",
    defer_low_priority=True,
    explore_remaining=False,
)

DEEP = SearchMode(
    name="deep",
    defer_low_priority=False,
    explore_remaining=True,
)

SEARCH_MODES = {
    SURFACE.name: SURFACE,
    DEEP.name: DEEP,
}


def get_search_mode(name="surface"):
    """Return a supported search mode without changing crawl limits."""
    try:
        return SEARCH_MODES[name]
    except (KeyError, TypeError):
        raise ValueError(f"Unsupported search mode: {name}") from None
