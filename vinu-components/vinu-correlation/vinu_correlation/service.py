from __future__ import annotations

from pathlib import Path
from typing import Any

from vinu_correlation.api import CorrelationAPI
from vinu_correlation.config import VinuCorrelationConfig, load_config


class CorrelationService:
    def __init__(self, config: VinuCorrelationConfig | None = None):
        self._config = config or load_config()
        self._api = CorrelationAPI(self._config)

    @property
    def api(self) -> CorrelationAPI:
        return self._api

    @property
    def config(self) -> VinuCorrelationConfig:
        return self._config

    def get_impact(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_impact(symbol, from_ts, to_ts)

    def get_events(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> list[dict[str, Any]]:
        return self._api.get_events(symbol, from_ts, to_ts)

    def get_correlation(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_correlation(symbol, from_ts, to_ts)

    def get_drawdown(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_drawdown(symbol, from_ts, to_ts)

    def get_baseline(self, symbol: str) -> dict[str, Any]:
        return self._api.get_baseline(symbol)

    def compute(self, symbol: str, incremental: bool = True):
        self._api.compute_and_store(symbol, incremental=incremental)

    def close(self):
        pass
