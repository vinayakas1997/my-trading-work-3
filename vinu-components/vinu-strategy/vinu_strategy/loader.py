from __future__ import annotations

from pathlib import Path

from vinu_strategy.engine.registry import StrategyRegistry
from vinu_strategy.models.strategy import StrategyConfig

_DEFAULT_STRATEGIES_DIR = Path(__file__).resolve().parent.parent / "strategies"

_registry: StrategyRegistry | None = None


def _get_registry() -> StrategyRegistry:
    global _registry
    if _registry is None:
        _registry = StrategyRegistry(_DEFAULT_STRATEGIES_DIR)
        _registry.load_all()
    return _registry


def load_strategy(name: str) -> StrategyConfig | None:
    return _get_registry().get(name)


def list_strategies() -> list[str]:
    return _get_registry().list()


def reload_strategies() -> dict[str, StrategyConfig]:
    return _get_registry().reload()
