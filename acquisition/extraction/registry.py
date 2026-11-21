"""Registry for document extraction strategies."""

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Strategy:
    name: str
    content_types: tuple[str, ...]
    extract: Callable
    required_config: tuple[str, ...] = ()
    prepare_kwargs: Callable[[dict], dict] | None = None

    def missing_config(self, config: dict) -> tuple[str, ...]:
        """Identify required configuration values not supplied."""
        return tuple(
            key
            for key in self.required_config
            if config.get(key) is None
        )


class StrategyRegistry:
    """Register and discover compatible extraction strategies."""

    def __init__(self):
        self._strategies: dict[str, Strategy] = {}

    def register(self, strategy: Strategy):
        if not strategy.name:
            raise ValueError("Strategy name is required")

        if strategy.name in self._strategies:
            raise ValueError(
                f"Strategy already registered: {strategy.name}"
            )

        self._strategies[strategy.name] = strategy

    def get(self, name: str) -> Strategy | None:
        return self._strategies.get(name)

    def compatible(self, content_type: str) -> list[Strategy]:
        normalized = content_type.split(";")[0].strip().lower()

        return [
            strategy
            for strategy in self._strategies.values()
            if normalized in strategy.content_types
        ]

    def names(self) -> list[str]:
        return list(self._strategies)
