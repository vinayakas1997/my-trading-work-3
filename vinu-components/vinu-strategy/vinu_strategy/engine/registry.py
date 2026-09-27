from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from vinu_strategy.models.strategy import StrategyConfig

LOG = logging.getLogger(__name__)


class StrategyRegistry:
    def __init__(self, strategies_dir: Path):
        self._strategies_dir = strategies_dir
        self._strategies: dict[str, StrategyConfig] = {}

    def load_all(self) -> dict[str, StrategyConfig]:
        # Built in a local dict and swapped in with one assignment at the
        # end -- a request served concurrently with a reload (get()/list()
        # from another thread) sees either the fully-old or fully-new
        # registry, never a partially-repopulated one where a strategy that
        # exists momentarily looks gone because this loop hasn't reached it
        # yet.
        loaded: dict[str, StrategyConfig] = {}
        if not self._strategies_dir.exists():
            LOG.warning("Strategies dir %s does not exist", self._strategies_dir)
            self._strategies = loaded
            return self._strategies

        for yaml_file in sorted(self._strategies_dir.glob("*.yaml")):
            try:
                with open(yaml_file) as f:
                    data: dict[str, Any] = yaml.safe_load(f)
                if not data or "name" not in data:
                    LOG.warning("Skipping %s: no 'name' field", yaml_file)
                    continue
                config = StrategyConfig.from_dict(data, source=str(yaml_file))
                loaded[config.name] = config
                LOG.info("Loaded strategy '%s' from %s", config.name, yaml_file)
            except Exception as e:
                LOG.error("Failed to load %s: %s", yaml_file, e)

        self._strategies = loaded
        return self._strategies

    def get(self, name: str) -> StrategyConfig | None:
        return self._strategies.get(name)

    def list(self) -> list[str]:
        return list(self._strategies.keys())

    def reload(self) -> dict[str, StrategyConfig]:
        return self.load_all()
