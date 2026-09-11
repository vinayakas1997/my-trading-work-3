"""StockService orchestrator for backfill, live ingest, and query."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import duckdb

LOG = logging.getLogger(__name__)
from vinu_stock.backfill.orchestrator import BackfillSummary, run_backfill
from vinu_stock.config import VinuStockConfig, load_config
from vinu_stock.events.finnhub_provider import FinnhubCalendarProvider
from vinu_stock.events.poller import refresh_calendar
from vinu_stock.events.store import EventsStore
from vinu_stock.live.ingest_cycle import LiveIngestSummary, run_live_cycle
from vinu_stock.providers.quote import AlpacaQuoteProvider
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
        # how-to-make-it-live.md #13: order-time NBBO reads for vinu-live's
        # spread gate. Cached with a short TTL below so a burst of entry
        # attempts in one cycle collapses to a single upstream call.
        self._quote_provider = AlpacaQuoteProvider(self._config)
        self._quote_cache: dict[str, tuple[dict[str, Any], float]] = {}
        # how-to-make-it-live.md #2: event-risk calendar. Own SQLite file next
        # to the meta db; refreshed daily by the ingest worker (refresh_events),
        # read at order time by vinu-live via /stock/events/{symbol}.
        self._events_store = EventsStore(str(self._config.data_root / "vinu_events.db"))
        self._calendar_provider = FinnhubCalendarProvider(self._config.finnhub_api_key)
        self._duckdb_conn = duckdb.connect()
        # data_root is resolved from the environment (VINU_STOCK_DATA_ROOT via
        # load_config()) -- the environment is the source of truth, NOT the
        # persisted vinu_settings row. A stale row (e.g. a Windows host path
        # seeded by a prior host-side run) used to silently override the
        # container's /data mount and make every candle query return empty.
        # Runtime PATCH /stock/settings data_root changes still apply
        # in-process; the env value re-asserts on the next start.
        self._data_root: Path = self._config.data_root

    @property
    def data_root(self) -> Path:
        return self._data_root

    def close(self) -> None:
        if hasattr(self, "_duckdb_conn") and self._duckdb_conn:
            try:
                self._duckdb_conn.close()
            except Exception:
                pass
        if hasattr(self, "_events_store"):
            try:
                self._events_store.close()
            except Exception:
                pass
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
        result = self._backend.patch_settings(
            poll_interval_sec=poll_interval_sec,
            default_provider=default_provider,
            data_root=data_root,
        )
        if data_root is not None:
            self._data_root = Path(data_root)
        return result

    def get_watchlist(self) -> list[str]:
        return self._backend.get_watchlist()

    def add_watchlist_tickers(self, tickers: list[str]) -> list[str]:
        added = self._backend.add_watchlist_tickers(tickers)
        self._export_watchlist_to_shared()
        return added

    def remove_watchlist_ticker(self, ticker: str) -> bool:
        return self._backend.remove_watchlist_ticker(ticker)

    def _export_watchlist_to_shared(self) -> None:
        path = self._config.shared_watchlist_path
        if path is None:
            return
        from vinu_stock.watchlist.shared import write_shared

        write_shared(path, self.get_watchlist())

    def sync_watchlist_from_shared(self) -> dict[str, object]:
        path = self._config.shared_watchlist_path
        if path is None:
            return {"ok": False, "message": "VINU_SHARED_WATCHLIST_PATH not set", "added": []}
        from vinu_stock.watchlist.shared import sync_from_shared

        added = sync_from_shared(self._backend.watchlist, path)
        return {"ok": True, "added": added, "tickers": self.get_watchlist()}

    def get_pending_backfill_symbols(self) -> list[str]:
        """Watchlist symbols with no catalog entry yet, or an incomplete backfill."""
        pending = []
        for sym in self.get_watchlist():
            entry = self._backend.catalog.get_symbol(sym)
            if entry is None or entry.backfill_status != "complete":
                pending.append(sym)
        return pending

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
        dry_run: bool = False,
    ) -> BackfillCycleResult:
        if dry_run:
            LOG.info("DRY RUN: run_backfill(%s) — skipping", symbols)
            return BackfillCycleResult(summary=BackfillSummary(years_ok=[], years_failed=[], total_rows=0))

        syms = symbols or self.get_pending_backfill_symbols()
        summary = run_backfill(
            syms,
            data_root=self.data_root,
            backend=self._backend,
            registry=self._registry,
            from_year=from_year,
            to_year=to_year,
        )
        return BackfillCycleResult(summary=summary)

    def run_live_cycle(self, symbols: list[str] | None = None, dry_run: bool = False) -> LiveCycleResult:
        if dry_run:
            LOG.info("DRY RUN: run_live_cycle(%s) — skipping", symbols)
            return LiveCycleResult(summary=LiveIngestSummary(bars_added=0, symbols_failed=0, symbols_polled=0), watchlist_size=0)

        syms = symbols or self.get_watchlist()
        summary = run_live_cycle(
            syms,
            data_root=self.data_root,
            backend=self._backend,
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
        adjusted: bool = True,
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
            connection=self._duckdb_conn,
        )

    # A full-market scanner (vinu-screener) polling ~8000 symbols with no
    # bulk endpoint means one HTTP round-trip per symbol per cycle -- found
    # while building vinu-screener's data-source adapter, and mitigated
    # there (timeout guard, coarse pre-filter, a rate-limit-floored poll
    # interval) but never actually fixed at the source. This is the fix:
    # collapse N round-trips into 1. Capped so one request can't block the
    # event loop indefinitely on a pathologically large symbol list.
    MAX_BATCH_SYMBOLS = 500

    def get_candles_batch(
        self,
        symbols: list[str],
        *,
        interval: str = "1m",
        from_ts: int | None = None,
        to_ts: int | None = None,
        days: int | None = None,
        provider: str | None = None,
        limit: int = 5000,
        indicators: list[str] | None = None,
        adjusted: bool = True,
    ) -> dict[str, list[dict[str, Any]]]:
        """Same per-symbol semantics as `get_candles()`, called once per
        symbol under the hood (the per-symbol storage layer isn't changed
        by this -- `_load_symbol_frame` is still one file per symbol) --
        the win is entirely on the network side: a caller that used to make
        len(symbols) HTTP calls now makes one. One bad symbol (unknown,
        empty history, a storage read error) yields an empty list for that
        symbol only; it never fails the whole batch."""
        out: dict[str, list[dict[str, Any]]] = {}
        for symbol in symbols:
            try:
                out[symbol.upper()] = self.get_candles(
                    symbol, interval=interval, from_ts=from_ts, to_ts=to_ts, days=days,
                    provider=provider, limit=limit, indicators=indicators, adjusted=adjusted,
                )
            except Exception:
                LOG.exception("candles batch: %s failed, returning empty for this symbol only", symbol.upper())
                out[symbol.upper()] = []
        return out

    _QUOTE_TTL_SEC = 5.0

    def get_quote(self, symbol: str) -> dict[str, Any]:
        """Latest bid/ask/spread for `symbol` (how-to-make-it-live.md #13).
        In-process TTL cache: repeated calls within _QUOTE_TTL_SEC return the
        same payload, so a cycle that attempts several entries hits the
        upstream data API once. A failed fetch is cached too -- if the venue
        is unreachable, do not hammer it once per entry; the consumer fails
        open on `ok: false` regardless."""
        sym = symbol.strip().upper()
        now = time.monotonic()
        cached = self._quote_cache.get(sym)
        if cached is not None and (now - cached[1]) < self._QUOTE_TTL_SEC:
            return cached[0]
        result = self._quote_provider.get_quote(sym)
        payload: dict[str, Any] = {
            "symbol": sym,
            "ok": result.success,
            "bid": result.bid,
            "ask": result.ask,
            "mid": result.mid,
            "spread_bps": result.spread_bps,
            "ts": result.ts,
            "error": result.error,
        }
        self._quote_cache[sym] = (payload, now)
        return payload

    # --- Event-risk calendar (how-to-make-it-live.md #2) --------------------

    def get_events(self, symbol: str, *, within_hours: float = 48.0) -> dict[str, Any]:
        """Upcoming earnings / macro events for `symbol` inside the next
        `within_hours`. `blackout` is True iff at least one is found -- the
        field vinu-live's entry guard reads. Always succeeds; an empty /
        unconfigured calendar just yields `blackout: false`."""
        sym = symbol.strip().upper()
        now = time.time()
        rows = self._events_store.upcoming(sym, now, now + within_hours * 3600.0)
        return {
            "symbol": sym,
            "within_hours": within_hours,
            "blackout": bool(rows),
            "events": rows,
            "configured": self._calendar_provider.is_configured(),
        }

    def refresh_events(self) -> dict[str, Any]:
        """Opportunistic daily calendar pull, called from the ingest worker
        loop. No-ops unless a `kind`'s last pull is older than
        VINU_EVENTS_REFRESH_HOURS. Never raises."""
        return refresh_calendar(
            self._events_store,
            self._calendar_provider,
            self.get_watchlist(),
            macro_enabled=self._config.events_macro_enabled,
            min_interval_hours=self._config.events_refresh_hours,
        )

    def health(self) -> dict[str, Any]:
        info = self._backend.health_info(self.data_root)
        info["providers"] = self._registry.provider_status()
        info["events"] = {
            "configured": self._calendar_provider.is_configured(),
            "rows": self._events_store.count(),
            "last_pull_earnings": self._events_store.get_last_pull("earnings"),
            "last_pull_economic": self._events_store.get_last_pull("economic"),
        }
        return info
