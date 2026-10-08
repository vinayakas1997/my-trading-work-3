# Data audit: vinu-stock-price

Checked 2026-10-08 on the running stack (`stock-api`; databases `vinu_stock_price.db`, `vinu_events.db`, `vinu_spreads.db`; files under `data/stock-price/prices/`).

## What triggers it
- **Ingest loop** (`vinu-stock-ingest --interval 60`, one batch call for all 50 symbols every minute): fetches 1-minute bars from Alpaca (IEX feed, `adjustment=all`), appends to the live file, logs one row per symbol.
- **Backfill** (once per symbol and year, 2022 onward): done for all 50 (250 year-jobs, 18 runs).
- **Events pull** (earnings calendar) and **quote recorder** (spread snapshots, only while someone asks for a quote or the recorder loop runs).

## Data items

### S1 Price bars  files `prices/1m/<SYMBOL>/archive/<year>.parquet` + `live/` (250 MB, 50 symbols, 2022-01 to now)
- **Format:** 1-minute rows `symbol, provider, bar_ts (unix s), open, high, low, close, volume, adj_factor`. Example: AAPL 1m, close 336.68, volume 33,532. Every other bar size (5m, 15m, 1h, 1d) is built from these on request; none is stored.
- **Access:** `GET /stock/candles/{symbol}` (interval, from/to, days, session, closed_only, as_of clamp, indicators, adjusted; paging by `next_from`), `POST /stock/candles/batch`.
- **Consumers (found in code):** screener (`data_source.py` batch), initial-analysis (`price_client.py`, all angles), tools/features (`client/stock_price.py`), live (`scheduler.py` prices and exits, `live_decision/bars_client.py`), agent (`stock_price_tool`, `trade_plan_tool`, `factor_backtest_tool`, `historical_broker`, memory sync), portfolio (`service.py`, `historical_simulation.py`), simulator (via config URL), news (price reaction), watchdog script.
- **Verdict:** `used well`, the most used data in the system.

### S2 Catalog  `symbol_catalog` (50 rows)
- **Format:** `symbol, provider, first_bar_ts, last_bar_ts, archive_through, backfill_status, has_adj_data, gap_count, last_validation_at`. Example: AAPL alpaca, first 2022-01-03, last 2026-10-08 04:55, complete, gap_count 2,046.
- **Access:** `GET /stock/catalog`, `/stock/catalog/{symbol}`.
- **Consumers:** research `bar_validation.py` (is the symbol complete, how fresh, how much history, gates a research run); scripts `pipeline_health.py`, `sync_universe.py`; reflection `ingest_health.py` (reads the database file directly).
- **Gaps in the data:** `gap_count` totals 542,317 over 50 symbols (about 10,800 each) and only reflection looks at it, and only to print it; nobody decides anything from it. `has_adj_data` is 0 for all 50 although the bars are requested with `adjustment=all` and the column is never read: it is a stale field.
- **Verdict:** `used well` for freshness/history; `no reader` for gaps and `has_adj_data`.

### S3 Ingest log  `ingest_log` (217,350 rows in about 3 days)
- **Producer:** every minute, one row per symbol (bars added, window, ok, error). 200 rows are failures from one DNS outage on 2026-10-07 23:37, each holding a 1-2 KB error text.
- **Consumers:** reflection `ingest_health` (via `list_ingest_log`, per symbol, to mark bad days). Nothing else.
- **Properties:** no pruning anywhere; about 72,000 rows a day, so 26 million a year.
- **Verdict:** `single use`, and unbounded (DA-S3).

### S4 Backfill records  `backfill_jobs` (250), `backfill_runs` (18), `provider_fallback_log` (0)
- **Access:** `GET /stock/backfill/runs`, `/stock/backfill/status/{id}`. **Consumers:** none found (reflection reads `provider_fallback_log`, which is empty because no fallback provider has ever been used). **Verdict:** `no reader` (control data; fine).

### S5 Quote and spread  `GET /stock/quote/{symbol}` (live call to Alpaca), `vinu_spreads.db spread_snapshots` (3,113 rows)
- **Format:** quote `{ok, bid, ask, mid, spread_bps}`. Snapshots by session: regular 1,434 (median 25 bps, p90 577), after-hours 697 and overnight 989 (both median 1,022 bps, p90 1,089, identical to many decimals).
- **Consumers:** live `guards.py` (`fetch_quote_snapshot`: spread guard, extended-hours limit price base, slippage mid), `scheduler.py` (entry and exit slices), trade-plan orchestrator (`fetch_spread_bps`). The snapshots table feeds `/stock/spread-stats`, whose only mentioned user is a comment in the simulator's cost model (`costs.py`): the simulator uses published figures instead (problem-log O10).
- **Gaps:** a real call for AAPL at 05:00 UTC returned `ok: false, bid 320.06, ask 0.0 "no valid two-sided quote"`. Outside regular hours the IEX feed gives no usable two-sided quote, and the live spread guard fails open on `None`, so in the extended sessions that matter for 24-hour trading the spread guard does not protect (DA-S5). The after-hours and overnight statistics are identical, so they are one stale quote counted twice, and they are not a spread.
- **Verdict:** regular hours `used well`; extended hours `wrong data` (feed limit).

### S6 Events  `vinu_events.db`: `events` (39 upcoming earnings), `events_archive` (48 past)
- **Format:** `symbol, kind (earnings only), event_ts, title, severity`. Next 28 days.
- **Access:** `GET /stock/events/{symbol}` (blackout flag).
- **Consumers:** live `event_blackout_reason` (entries and scheduler slices); reflection `event_holding_loss` (archive, direct file); research `bar_validation`/costs mention events through the blackout. Only earnings are pulled; the code names other macro kinds (Finnhub) but none are stored (DA-S6).
- **Verdict:** `used well` for earnings; macro events `not stored`.

### S7 Settings and watchlist  `vinu_settings` (3), `watchlist_tickers` (50) and `data/shared/watchlist.json`
- Shared with news. `used well` (control data). The shared file shows as modified in git with 50 symbols and is not committed.
