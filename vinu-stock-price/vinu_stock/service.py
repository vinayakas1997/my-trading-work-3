"""StockService orchestrator for backfill, live ingest, and query."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from vinu_stock.backfill.orchestrator import BackfillSummary, run_backfill
from vinu_stock.config import VinuStockConfig, load_config
from vinu_stock.live.ingest_cycle import LiveIngestSummary, run_live_cycle
from vinu_stock.providers.registry import ProviderRegistry
from vinu_stock.query.engine import fetch_candles
from vinu_stock.settings.store import SettingsView
from vinu_stock.storage.backend import MetaBackend


@dataclass
class BackfillCycleResult:
    summary: BackfillSummary

    def format_report(self) -> str:
        return self.summary.format_report()


@dataclass
class LiveCycleResult:
    summary: LiveIngestSummary
    watchlist_size: int

    def format_report(self) -> str:
        lines = [f"Watchlist: {self.watchlist_size} tickers", self.summary.format_report()]
        return "\n".join(lines)


class StockService:
    def __init__(
        self,
        backend: MetaBackend | None = None,
        config: VinuStockConfig | None = None,
    ) -> None:
        self._config = config or load_config()
        self._backend = backend or MetaBackend(self._config.meta_db_path)
        self._owns_backend = backend is None
        self._registry = ProviderRegistry(self._config)

    @property
    def data_root(self) -> Path:
        settings = self._backend.get_settings()
        return Path(settings.data_root)

    def close(self) -> None:
        if self._owns_backend:
            self._backend.close()

    def __enter__(self) -> StockService:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_settings(self) -> SettingsView:
        return self._backend.get_settings()

    def patch_settings(
        self,
        *,
        poll_interval_sec: int | None = None,
        default_provider: str | None = None,
        data_root: str | None = None,
    ) -> SettingsView:
        return self._backend.patch_settings(
            poll_interval_sec=poll_interval_sec,
            default_provider=default_provider,
            data_root=data_root,
        )

    def get_watchlist(self) -> list[str]:
        return self._backend.get_watchlist()

    def add_watchlist_tickers(self, tickers: list[str]) -> list[str]:
        return self._backend.add_watchlist_tickers(tickers)

    def remove_watchlist_ticker(self, ticker: str) -> bool:
        return self._backend.remove_watchlist_ticker(ticker)

    def sync_watchlist_from_shared(self) -> dict[str, object]:
        path = self._config.shared_watchlist_path
        if path is None:
            return {"ok": False, "message": "VINU_SHARED_WATCHLIST_PATH not set", "added": []}
        from vinu_stock.watchlist.shared import sync_from_shared

        added = sync_from_shared(self._backend.watchlist, path)
        return {"ok": True, "added": added, "tickers": self.get_watchlist()}

    def get_catalog(self, symbol: str | None = None) -> list[dict[str, Any]]:
        if symbol:
            entry = self._backend.catalog.get_symbol(symbol)
            return [entry.to_dict()] if entry else []
        return [e.to_dict() for e in self._backend.catalog.list_symbols()]

    def run_backfill(
        self,
        symbols: list[str] | None = None,
        *,
        from_year: int | None = None,
        to_year: int | None = None,
    ) -> BackfillCycleResult:
        syms = symbols or self.get_watchlist()
        summary = run_backfill(
            syms,
            data_root=self.data_root,
            catalog=self._backend.catalog,
            registry=self._registry,
            from_year=from_year,
            to_year=to_year,
        )
        return BackfillCycleResult(summary=summary)

    def run_live_cycle(self, symbols: list[str] | None = None) -> LiveCycleResult:
        syms = symbols or self.get_watchlist()
        summary = run_live_cycle(
            syms,
            data_root=self.data_root,
            catalog=self._backend.catalog,
            registry=self._registry,
        )
        return LiveCycleResult(summary=summary, watchlist_size=len(syms))

    def get_candles(
        self,
        symbol: str,
        *,
        interval: str = "1m",
        from_ts: int | None = None,
        to_ts: int | None = None,
        days: int | None = None,
        provider: str | None = None,
        limit: int = 5000,
        indicators: list[str] | None = None,
        adjusted: bool = False,
    ) -> list[dict[str, Any]]:
        end_ts = to_ts
        start_ts = from_ts
        if days is not None and start_ts is None:
            end = datetime.now(timezone.utc) if end_ts is None else datetime.fromtimestamp(end_ts, tz=timezone.utc)
            start = end - timedelta(days=max(1, days))
            start_ts = int(start.timestamp())
            end_ts = int(end.timestamp())
        return fetch_candles(
            self.data_root,
            symbol,
            interval=interval,
            from_ts=start_ts,
            to_ts=end_ts,
            provider=provider,
            limit=limit,
            indicators=indicators,
            adjusted=adjusted,
        )

    def health(self) -> dict[str, Any]:
        info = self._backend.health_info(self.data_root)
        info["providers"] = self._registry.provider_status()
        return info
