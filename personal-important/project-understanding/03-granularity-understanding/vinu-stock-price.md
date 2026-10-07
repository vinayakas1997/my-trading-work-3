# vinu-stock-price

## What it is

Owns all price/candle data — fetches it from real providers, stores it as
parquet, serves it back to every other service over HTTP. Nothing else in
Vina talks to Alpaca/Polygon/Yahoo/Tushare directly for price data; this
is the one place that does.

## Trigger / cadence

Two independent loops, run as two separate processes (`cli.py`'s
`ingest_main` / `serve_main`):

1. **Ingest worker** (`vinu-stock ingest --continuous`): a `while True`
   loop, sleeping `service.get_settings().poll_interval_sec` between
   iterations. Default **60 seconds** — `DEFAULT_POLL_INTERVAL_SEC = 60`
   in `config.py`, overridable via `VINU_STOCK_POLL_INTERVAL_SEC`. This is
   the literal "Alpaca get price 1-minute" cadence.
2. **HTTP API** (`vinu-stock serve`, FastAPI via `server/app.py`): always
   up, answers on-demand reads from every other service.

## Pipeline

**Each ingest cycle** (`cli.py::ingest_main`'s loop body, in order):
1. `service.sync_watchlist_from_shared()` — pulls new tickers from the
   shared cross-service watchlist file (`VINU_SHARED_WATCHLIST_PATH`,
   `watchlist/shared.py::sync_from_shared`) into this service's own
   `WatchlistStore`. This is how a ticker added via `vinu-agent`'s
   `/track` command (or anywhere else) actually starts getting priced.
2. `service.get_pending_backfill_symbols()` → if any, `service.run_backfill(...)`
   — a brand-new symbol has no history yet; this fills it in (see
   Backfill below) before the live loop bothers polling it.
3. `service.run_live_cycle()` (`service.py:185`) — the actual 1-minute
   ingest, per watched symbol, **in parallel** (`ingest_cycle.py`'s
   `_ingest_symbol`, run via `concurrent.futures`):
   - Look up `last_bar_ts` for the symbol from the catalog (SQLite,
     `catalog/store.py`).
   - `registry.fetch_bars_with_fallback(sym, start_ts, now_ts, role="live")`
     — start_ts is `last_bar_ts - OVERLAP_SEC(180s)` (re-fetches a small
     overlap window in case the last poll's tail bar wasn't closed yet),
     or `now - 24h` on a cold start.
   - `_filter_closed_bars` — **only bars whose minute has fully closed**
     (`bar_ts + 60 <= now`) are kept; the current, still-forming minute is
     never ingested as if it were final.
   - New bars appended to this year's live parquet file
     (`storage/paths.py::live_year_path`), catalog's `last_bar_ts`
     advanced, `catalog.log_ingest(...)` records the attempt (success or
     failure) for observability.
4. `service.refresh_events()` — opportunistic, best-effort, non-fatal
   (wrapped in try/except so it can never kill the ingest loop): pulls
   Finnhub's economic/earnings calendar (`events/poller.py::refresh_calendar`,
   `events/finnhub_provider.py`) if the last pull for that calendar kind
   is stale. This is the `/stock/events/{symbol}` blackout-window data
   `vinu-live`'s entry guard reads.
5. Sleep `poll_interval_sec`, repeat.

**Provider fallback** (`providers/registry.py::fetch_bars_with_fallback`):
tries providers in order for the given role — default chain for US equity
is `alpaca → polygon → tushare → yahoo` (`FALLBACK_CHAINS["us_equity"]`,
overridable via `VINU_PROVIDER_ORDER`). Alpaca is first because it's the
one also used for the real broker connection (`vinu-agent`) — same data
source as what actually executes.

**Backfill** (`backfill/orchestrator.py::run_backfill`, invoked for a
pending new symbol): `_discover_first_year` (earliest year the provider
has data for) → `_backfill_symbol` fetches and writes year-by-year archive
parquet files (`storage/paths.py::archive_year_path`) → 
`_consolidate_current_year` / `_rollover_previous_years` reconcile the
live-vs-archive split so a year that's fully in the past moves out of the
"live" file into the permanent archive.

**Reads** (`server/routes_read.py`, what everything else actually calls):
- `GET /stock/quote/{symbol}` — latest quote.
- `GET /stock/candles/{symbol}?interval=&days=&adjusted=` — the one
  `vinu-live`'s orchestrator hits every cycle for both spot price and
  historical-returns lookback (`query/engine.py::fetch_candles` reads the
  parquet files via a cached, signature-invalidated in-memory frame —
  `_file_signature`/`invalidate_symbol_cache` — then `query/aggregate.py`
  buckets 1m bars up to the requested interval, `query/indicators.py`
  optionally attaches SMA/RSI/MACD/ADX/etc. computed on the returned
  window when `indicators=` is passed).
- `POST /stock/candles/batch` — same as above, N symbols in one call
  (added specifically to remove the one-call-per-symbol bottleneck other
  services like `vinu-screener` were hitting).
- `GET /stock/events/{symbol}?within_hours=` — blackout-window check.
- `GET /stock/catalog[/{symbol}]` — what data actually exists, for
  observability/debugging, not used in the trading hot path.

## Storage

- Parquet, split live year vs archived years, one directory per symbol
  (`storage/paths.py`): `{data_root}/prices/{symbol}/live/{year}.parquet`
  and `{data_root}/prices/{symbol}/archive/{year}.parquet`.
- A SQLite catalog (`catalog/store.py`) tracking, per symbol: first/last
  bar timestamp, last ingest attempt (ok/error), used both to drive the
  incremental live-cycle fetch window and to answer `/stock/catalog`.

## Talks to

- **Outbound**: Alpaca / Polygon / Tushare / Yahoo (real market-data
  providers), Finnhub (economic calendar).
- **Inbound**: every other service reads price data from here —
  `vinu-live` (spot price + returns), `vinu-initial-analysis`/`vinu-research`
  (historical series for analysis), `vinu-screener` (universe scans),
  `vinu-agent` (Telegram `/rank` formatting uses screener data, but
  candle-derived fields ultimately trace back here too).
- Shared watchlist file is the one loose coupling to `vinu-news`/`vinu-agent` —
  no direct HTTP call, a shared file both sides read/write with a lock
  (`watchlist/shared.py`).
