"""InitialAnalysisService facade — wraps AngleRunner with health, dry-run, and lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from vinu_initial_analysis.api import CorrelationAPI
from vinu_initial_analysis.config import VinuInitialAnalysisConfig, load_config
from vinu_initial_analysis.runner import AngleRunner
from vinu_initial_analysis.storage.parquet import AngleStorage

LOG = logging.getLogger(__name__)


class InitialAnalysisService:
    def __init__(self, config: VinuInitialAnalysisConfig | None = None):
        self._config = config or load_config()
        self._api = CorrelationAPI(self._config)

    @property
    def api(self) -> CorrelationAPI:
        return self._api

    @property
    def runner(self) -> AngleRunner:
        return self._api.runner

    @property
    def storage(self) -> AngleStorage:
        return self._api.storage

    @property
    def config(self) -> VinuInitialAnalysisConfig:
        return self._config

    # -- backward-compat alias methods -------------------------------------

    def get_impact(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_impact(symbol, from_ts, to_ts)

    def get_events(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> list[dict[str, Any]]:
        return self._api.get_events(symbol, from_ts, to_ts)

    def get_correlation(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_correlation(symbol, from_ts, to_ts)

    def get_drawdown(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_drawdown(symbol, from_ts, to_ts)

    def get_story(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_story(symbol, from_ts, to_ts)

    def get_batch(self, symbols: list[str], from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_batch(symbols, from_ts, to_ts)

    def compute(self, symbol: str, dry_run: bool = False):
        if dry_run:
            LOG.info("DRY RUN: compute(%s) — skipping persist", symbol)
            return
        self._api.compute_and_store(symbol)

    def run_analysis(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        """Run all available angles for a symbol. Returns summary."""
        return self._api.compute_and_store(symbol, from_ts=from_ts, to_ts=to_ts)

    def list_angles(self) -> list[dict[str, Any]]:
        return self._api.runner.list_angles()

    def list_symbols(self) -> list[str]:
        return self._api.storage.list_symbols()

    def health(self) -> dict[str, Any]:
        try:
            db_path = str(self._config.data_root)
            symbols = len(self._api.storage.list_symbols())
        except Exception:
            db_path = str(self._config.data_root)
            symbols = 0
        return {
            "status": "ok",
            "service": "vinu-initial-analysis",
            "news_api_url": self._config.news_api_url,
            "stock_api_url": self._config.stock_api_url,
            "data_root": db_path,
            "symbols_with_data": symbols,
        }

    def close(self):
        self._api.close()

    def __enter__(self) -> InitialAnalysisService:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
