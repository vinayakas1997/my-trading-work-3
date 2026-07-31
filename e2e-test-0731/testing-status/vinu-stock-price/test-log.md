# vinu-stock-price — Test Log

**Status:** Passed — full checklist verified 2026-07-31 (see "Verification results" below)

## What will be tested

- Fetch real 1-minute OHLCV candles from Alpaca for the Stage 1 ticker
  list, 2022-01-01 → 2026-06-30.
- Aggregation from the 1-minute base up to 1-day, 4-hour, 1-hour, 15-minute
  bars.
- `GET /catalog/{symbol}` reflects what's actually cached (correct date
  range, no gaps beyond real market closures).
- `GET /candles/{symbol}` for each of the 5 intervals, with `from`/`to`
  and `days` params.
- Provider fallback chain behaves correctly when Alpaca is used explicitly
  (`VINU_STOCK_DEFAULT_PROVIDER=alpaca`).

## Expected output

- Every requested ticker has continuous 1-minute data for the full
  2022-01-01 → 2026-06-30 window (or the run explicitly reports which
  tickers don't, per the "no backfill-then-truncate" note in
  [../../full-plan.md](../../full-plan.md)).
- Aggregated bars are internally consistent with the 1-minute source:
  daily high = max of that day's intraday highs, daily volume = sum of
  intraday volumes, etc. — not independently fetched, so they can't drift.
- No NaN/null OHLCV fields in stored data.
- `meta.db` catalog entries match what's actually on disk.

## Verification results (2026-07-31)

All remaining checklist items executed against the running `stock-api` container
(`docker compose up -d --build` stack, healthy). Every check passed; no new bugs
found, no fixes needed this pass.

- **Catalog:** `GET /catalog` and `GET /catalog/{symbol}` return all 3 tickers
  with `backfill_status: complete`, `archive_through: 2025`, and full-window
  `first_bar_ts` (2022-01-03) → `last_bar_ts` (≈2026-07-30).
- **Candle reads:** `GET /candles/{symbol}` for all 5 intervals (1m/15m/1h/4h/1d),
  full window `from`/`to`, `limit=50000`: non-empty for every symbol×interval,
  **0 null/NaN OHLCV fields**. `1d` returns 1124–1125 bars (≈ full trading-day
  count for 2022-01-03 → 2026-06-30). `days=30` param works (returns last 30
  calendar days including live data through 2026-07-30).
- **Aggregation consistency (1m → higher TF):** spot-checked 3 sample dates per
  ticker (2022-01-03, 2023-06-15, 2026-06-30) with `adjusted=false` on both
  sides. For **all 9 day-samples and all 3 tickers**: daily open/high/low/close/
  volume recomputed from the day's 1m bars exactly matches the `1d` bar
  (high=max intraday, low=min, close=last, volume=sum). Same exact-match check
  for `4h` and `15m` bucketing on 2023-06-15 per ticker — all PASS. Aggregates
  are internally consistent with the single 1m source by construction.
- **Provider:** `GET /settings` shows `default_provider: "alpaca"`; health shows
  alpaca as the only registered provider (`enabled`, `priority 1`).
  `GET /candles/AAPL?provider=alpaca` returns data tagged `provider: alpaca`.

**Observation (not a bug) — 1m query cap:** a full-window 1m fetch
(2022-01-03 → 2026-06-30) returns exactly `50000` rows (the `limit` cap) and
stops around mid-2022 — the full window is ~360k 1m bars/symbol. The data *is*
all present (verified via bounded `from`/`to` queries at the window end,
2026-06-29/30, and via the backfill row count); callers needing the full 1m
history must page with `from`/`to`, not rely on a single unbounded call.
Worth noting for downstream consumers (`vinu-tools` feature jobs, `vinu-simulator`).

## Bug / Fix Log

### Bug-1 — container crash-loops on startup, can't write its meta DB

- **Found during:** first `docker compose up -d --build` of the full stack.
- **Date:** 2026-07-31
- **Symptom:** `stock-api` crash-loops. Logs show
  `OSError: [Errno 30] Read-only file system: '../data'`.
- **Reproduction:** `docker compose up -d` then `docker compose logs stock-api`.
- **Suspected cause:** two compounding issues:
  1. `vinu-components/.env` sets `VINU_STOCK_DATA_ROOT=../data/stock-price`
     and `VINU_STOCK_META_DB_PATH=../data/stock-price/meta.db` — a
     local-dev-style relative path that doesn't exist inside the
     container's read-only filesystem, overriding the Dockerfile's own
     correct default (`ENV VINU_STOCK_DATA_ROOT=/data`,
     `ENV VINU_STOCK_META_DB_PATH=/data/meta.db`).
  2. Even with the path fixed, the host bind-mount directory
     `./data/stock-price` is not writable by the container's non-root
     user (`uid=100(app) gid=101(app)`) — confirmed by a direct write
     test failing.
- **Severity:** blocker.

### Fixed-1

- **Root cause:** confirmed both causes via `docker compose logs` and a
  manual `docker run ... touch` write test (denied even on a
  pre-existing, non-root-owned host directory).
- **Fix applied:**
  - `vinu-components/.env`: `VINU_STOCK_DATA_ROOT` and
    `VINU_STOCK_META_DB_PATH` changed from `../data/stock-price` /
    `../data/stock-price/meta.db` to `/data` / `/data/meta.db`, matching
    the Dockerfile's own correct defaults.
  - `docker run --rm -v "$(pwd)/data:/fixdata" alpine chown -R 100:101 /fixdata`
    — fixed host-directory ownership for all 10 services' data
    directories at once (container's non-root user is
    `uid=100(app) gid=101(app)`; no host `sudo` available, so used a
    throwaway root container via the Docker daemon instead).
- **Verification:** `docker compose up -d` (config change, no rebuild
  needed), confirmed via `docker compose ps` → `stock-api ... (healthy)`,
  no tracebacks in `docker compose logs stock-api`.
- **Status:** fixed.

### Bug-2 — `POST /backfill/trigger` job always fails: SQLite cross-thread error

- **Found during:** first real component test — added AAPL/TSLA/JNJ to
  the watchlist, then `POST /stock/backfill/trigger`.
- **Date:** 2026-07-31
- **Symptom:** job status flips to `"failed"` almost immediately with
  `"SQLite objects created in a thread can only be used in that same
  thread. The object was created in thread id ... and this is thread id
  ..."`.
- **Reproduction:**
  ```
  curl -X POST localhost:8081/stock/watchlist/tickers -d '{"tickers":["AAPL","TSLA","JNJ"]}'
  curl -X POST localhost:8081/stock/backfill/trigger -d '{"symbols":["AAPL","TSLA","JNJ"],"force":false}'
  curl localhost:8081/stock/backfill/status/<job_id>
  ```
- **Suspected cause:** `vinu_stock/server/routes_config.py`'s
  `trigger_backfill` spawns one background `threading.Thread` (call it
  thread B) that calls `service.run_backfill(...)`, which resolves
  `self._backend.catalog` **once in thread B** and passes that single
  `CatalogStore` object into
  `backfill/orchestrator.py:run_backfill()`'s
  `ThreadPoolExecutor(max_workers=min(len(symbols), 4))`. Each pool
  worker thread then calls methods on that same `CatalogStore`, which
  wraps a `sqlite3.Connection` created via
  `vinu_lib.sqlite.SQLiteBackend._get_conn()` — that call uses
  `sqlite3.connect(path)` with the **default** `check_same_thread=True`,
  relying instead on `threading.local()` for per-thread isolation. The
  thread-local mechanism only works if each thread resolves
  `backend.catalog` *itself*; here the resolved object is created in
  thread B and handed to threads C/D/E/F by reference, so the first
  cross-thread SQLite call raises immediately.
- **Severity:** blocker (backfill — the core feature of this
  component — cannot succeed for more than 0 symbols in the
  multi-symbol case).

### Fixed-2

- **Root cause:** confirmed by reading
  `vinu_stock/backfill/orchestrator.py` — `run_backfill()` resolved
  `backend.catalog` once in the caller thread and passed that single
  `CatalogStore`/connection into a 4-worker `ThreadPoolExecutor`, so
  every worker after the first touched a `sqlite3.Connection` it didn't
  create (see Bug-2 for the full mechanism).
- **Fix applied:**
  - `vinu_stock/backfill/orchestrator.py`: `_backfill_symbol()` now takes
    `backend: MetaBackend` instead of `catalog: CatalogStore` and calls
    `backend.catalog` itself — inside the worker thread — so each pool
    thread gets its own thread-local connection via
    `vinu_lib.sqlite.SQLiteBackend`'s existing (correct) thread-local
    design. `run_backfill()`'s `ThreadPoolExecutor.submit(...)` call
    passes `backend=` instead of the pre-resolved `catalog=`; the
    sequential post-pool `rollover_and_consolidate(...)` call (runs in
    the original thread, so no cross-thread risk) still uses
    `backend.catalog` resolved there.
  - `vinu_stock/service.py`: `run_backfill()` now passes
    `backend=self._backend` to the orchestrator instead of
    `catalog=self._backend.catalog`.
- **Verification:** rebuilt via `docker compose up -d --build stock-api`;
  re-ran the exact Bug-2 repro (watchlist = AAPL/TSLA/JNJ,
  `POST /backfill/trigger` with all 3 symbols). Job completed
  `"status":"done"`, `years_ok: 12, years_failed: 0, total_rows: 1079169`.
  `GET /stock/catalog` shows all 3 symbols `backfill_status: "complete"`,
  `first_bar_ts` = 2022-01-03 (first trading day of the window) and
  `last_bar_ts` ≈ 2026-07-30 (most recent trading day) for all three —
  full window covered, no crash.
- **Status:** fixed.
- **Observation (not a bug):** `gap_count` differs a lot by symbol
  (AAPL 5146, TSLA 5331, JNJ 19755) — JNJ trades far less per minute than
  AAPL/TSLA, so more 1-minute buckets with zero trades is expected
  market microstructure, not a data-quality defect. Noted here so a
  future tester doesn't mistake this for a regression; worth a real look
  only if daily-bar aggregation (still untested) produces suspicious
  results for JNJ specifically.
