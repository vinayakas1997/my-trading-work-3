"""CorrelationService facade — wraps CorrelationAPI with health, dry-run, and lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from vinu_lib.client import ResilientClient
from vinu_correlation.api import CorrelationAPI
from vinu_correlation.config import VinuCorrelationConfig, load_config

LOG = logging.getLogger(__name__)


class CorrelationService:
    def __init__(self, config: VinuCorrelationConfig | None = None):
        self._config = config or load_config()
        self._api = CorrelationAPI(self._config)
        self._news_client = ResilientClient(self._config.news_api_url, "news", timeout=5.0)
        self._stock_client = ResilientClient(self._config.stock_api_url, "stock", timeout=5.0)

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

    def get_story(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_story(symbol, from_ts, to_ts)

    def get_batch(self, symbols: list[str], from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        return self._api.get_batch(symbols, from_ts, to_ts)

    def get_gap(self, symbol: str, date: str | None = None) -> dict[str, Any]:
        return self._api.get_gap(symbol, date)

    def compute(self, symbol: str, incremental: bool = True, dry_run: bool = False):
        if dry_run:
            LOG.info("DRY RUN: compute(%s, incremental=%s) — skipping persist", symbol, incremental)
            return
        self._api.compute_and_store(symbol, incremental=incremental)

    async def health(self) -> dict[str, Any]:
        news_ok = await self._news_client.health()
        stock_ok = await self._stock_client.health()
        try:
            db_path = str(self._config.data_root)
            total_events = len(self._api.storage.list_events()) if hasattr(self._api, "storage") else 0
        except Exception:
            db_path = str(self._config.data_root)
            total_events = 0
        return {
            "status": "ok",
            "service": "vinu-correlation",
            "news_api_healthy": news_ok,
            "stock_api_healthy": stock_ok,
            "db_path": db_path,
            "total_events": total_events,
        }

    async def close(self):
        await self._news_client.close()
        await self._stock_client.close()

    def __enter__(self) -> CorrelationService:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
