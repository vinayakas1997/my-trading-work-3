# vinu-tools (features-api) — Test Log

**Status:** Passed — full checklist verified 2026-07-31 (see "Verification results" below; 5 new bugs found & fixed: Bug-2/3/4/5/6, on top of the pre-existing Bug-1)

## What will be tested

- `GET /presets` lists the expected feature blueprints.
- `POST /requests` + `POST /requests/{id}/run` computes features from real
  `vinu-stock-price` candle data for the Stage 1 ticker list and date
  range.
- `GET /features/{symbol_or_kind}` retrieves the computed output correctly.
- Behavior when `vinu-stock-price` has partial or missing data for a
  requested symbol/range.

## Expected output

- Computed feature parquet files with no NaN/inf values beyond an
  expected warm-up window (e.g. first N rows of a moving-average feature).
- `manifest.md` per run accurately describes what was computed (symbol,
  date range, preset used).
- Feature values are sane for spot-checked dates (e.g. a 20-day SMA
  roughly matches a manual calculation from the same underlying candles).
- Clear error/status (not a silent wrong result) when upstream price data
  is incomplete.

## Verification results (2026-07-31)

- **`GET /presets`:** lists 11 blueprints (alpha101_benchmark 101,
  alpha158 158, alpha360 360, basic_ta, full_ta, mean_reversion_pack,
  momentum, swing_basic, trend_pack, volatility_pack, volume_pack) —
  correct.
- **`POST /requests` + `POST /requests/{id}/run`:** computed a real
  full-window job (request 1 `e2e-basic-ta-2022-2026`, AAPL/TSLA/JNJ,
  2022-01-01 → 2026-06-30, 1d, preset `basic_ta` = sma_20, rsi_14,
  daily_return) → `status: done`, 3,374 rows, artifact at
  `/data/runs/1_e2e_basic_ta_2022_2026/features.parquet`.
  - Parquet audit: per-symbol AAPL 1,125 / JNJ 1,124 / TSLA 1,125 rows;
    date range 2022-01-03 → 2026-06-30; **0 inf**; NaN only in the
    expected warm-up rows (sma_20 57 = 19/symbol, rsi_14 42 = 14/symbol,
    daily_return 3 = 1/symbol).
  - Spot-check: manual SMA-20 of AAPL close on 2026-06-30 computed from
    raw `vinu-stock-price` 1d candles = **296.673**, exact match to the
    parquet value. Feature math verified against real upstream data.
  - `manifest.md` now correctly reports `Status: done` (Bug-5 fix) and
    accurately lists symbol, ts range, interval, preset, features, rows.
- **`GET /features/{symbol_or_kind}`:** documented single-prefix path
  `/features/AAPL` → 200 with real values
  `{"sma_20": 297.57, "rsi_14": 46.93}`; parametrized kinds
  `rsi_14`/`sma_20` → 200 (Bug-2/3/4 fixes). Catalog at `/features/catalog`
  (24 indicators). No shadowing: `/factors`, `/factors/search`,
  `/factors/{id}`, `/ml/models`, `/presets`, `/requests`, `/health` all
  200.
- **Partial / missing upstream data (Bug-6 fix):** mixed request
  (AAPL + uncataloged SK) → `done`, 20 rows, SK skipped (graceful
  partial coverage). All-missing request (SPDR) → `failed` with clear
  `error_message: "No candle data returned for any requested symbol in
  the given range"`, no orphan artifact.
- **Unit tests:** full vinu-tools suite passes (118 passed) after
  updating 3 tests that had encoded the old double-prefixed URLs
  (`/features/features/AAPL` → `/features/AAPL`,
  `/features/features` → `/features/catalog`). Note: suite needs
  `--import-mode=importlib` locally (pre-existing collection quirk).
  vinu-research suite 535 passed (1 pre-existing unrelated failure:
  `TestScheduledExecutor::test_lazy_service_initialization`).
- **Consumers:** vinu-strategy's `FeaturesClient` (base = raw
  `features_api_url` + `/features/{symbol}`) now reaches the route it
  was written against; vinu-research's features client call path
  fixed to the prefix-once convention (cross-component, same root cause
  as Bug-2). Both containers rebuilt and healthy.
- **Checked, not a bug:** vinu-simulator's `FeaturesClient.get_indicators`
  calls `/features/indicators/{symbol}` — no such route exists in
  vinu-tools. Confirmed by reading `vinu_simulator/service.py:273-282`
  that this method is **dead code**: the real backtest path deliberately
  bypasses it (existing code comment explains the route only ever
  returns a latest-value snapshot, not a historical series) and instead
  gets indicator columns via `PriceClient.get_ohclv(..., indicators=...)`
  through stock-api's `/candles` endpoint. `get_indicators` is not called
  anywhere else in the service and has no test coverage. No fix needed;
  nothing further to do here when vinu-simulator is tested.
- **Note:** a stale pre-existing run artifact
  (`/data/runs/1_pipeline_run_jpm`, from 2026-07-23) was found in the
  features data dir — left untouched.

## Bug / Fix Log

### Bug-1 — container crash-loops on startup, can't write its meta DB

- **Found during:** first `docker compose up -d --build` of the full stack.
- **Date:** 2026-07-31
- **Symptom:** `features-api` crash-loops. Logs show
  `OSError: [Errno 30] Read-only file system: '/app/data'` /
  `FileNotFoundError: [Errno 2] No such file or directory: '/app/data/features'`.
- **Reproduction:** `docker compose up -d` then `docker compose logs features-api`.
- **Suspected cause:** `vinu-components/.env` sets
  `VINU_FEATURES_DATA_DIR=../data/features` and
  `VINU_FEATURES_META_DB_PATH=../data/features/meta.db` — local-dev-style
  relative paths overriding the Dockerfile's correct defaults
  (`ENV VINU_FEATURES_DATA_DIR=/data`, `ENV VINU_FEATURES_META_DB_PATH=/data/meta.db`).
  Same shared host-directory-permission issue as
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Bug-1 also applies here.
- **Severity:** blocker.

### Fixed-1

- **Root cause:** confirmed via `docker compose logs features-api` —
  same shared cause as
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Fixed-1.
- **Fix applied:** `vinu-components/.env`'s `VINU_FEATURES_DATA_DIR` and
  `VINU_FEATURES_META_DB_PATH` changed from `../data/features` /
  `../data/features/meta.db` to `/data` / `/data/meta.db`;
  host-directory ownership fixed via the shared `chown -R 100:101` fix.
- **Verification:** `docker compose ps` → `features-api ... (healthy)`,
  no tracebacks in `docker compose logs features-api`.
- **Status:** fixed.

### Bug-2 — `GET /features/{symbol}` is double-prefixed, returns 404

- **Found during:** checklist item "`GET /features/{symbol_or_kind}`
  retrieves the computed output correctly" — first probe of the symbol
  snapshot route.
- **Date:** 2026-07-31
- **Symptom:** `GET /features/AAPL` → `{"detail":"Not Found"}` HTTP 404.
  The documented/plan API surface
  ([../../scope-responsibilities/vinu-tools.md](../../scope-responsibilities/vinu-tools.md))
  is `GET /features/{symbol_or_kind}`, and vinu-strategy's
  `FeaturesClient.get_features` calls exactly that
  (`vinu_strategy/clients/features_client.py:23` with a prefix-free base
  URL). Only the accidental double-prefixed path works:
  `GET /features/features/AAPL`.
- **Reproduction:** `curl localhost:8082/features/AAPL`.
- **Suspected cause:** `vinu_tools/server/routes_features.py` defines
  `@router.get("/features")` and `@router.get("/features/{symbol_or_kind}")`
  while `vinu_tools/server/app.py` mounts the merged router under
  `route_prefix="features"` — so the real paths are
  `/features/features` and `/features/features/{symbol_or_kind}`. Same
  bug class as vinu-news Bug-4 (embedded prefix under an already-prefixed
  mount). The `/factors*` and `/ml/models` routes in the same file do
  NOT embed `/features` — only these two catalog/symbol routes do.
- **Consumer impact (cross-component):** vinu-strategy's
  `FeaturesClient` (base = raw `features_api_url` + path
  `/features/{symbol}`) → `/features/AAPL` → 404 → silently degrades to
  `{}`. vinu-research's `_features_client` (base `{url}/features` +
  path `/features/{symbol}`, `tools.py:215`) currently *matches* the
  broken double-prefixed route, so it "works" only because the route is
  wrong; per the shared convention (prefix appended once at
  construction, prefix-free call paths — see vinu-research/tools.py's
  own simulator/stock/correlation clients) it is also out of contract.
- **Severity:** blocker (documented API surface unreachable; strategy
  feature pipeline silent-empty).

### Bug-3 — symbol-snapshot inline stock fetch missing `/stock` prefix

- **Found during:** same checklist item, after manually confirming the
  double-prefixed route was the real one.
- **Date:** 2026-07-31
- **Symptom:** `GET /features/features/AAPL` → HTTP 502 with
  `Upstream stock-api error for AAPL: Client error '404 Not Found' for
  url 'http://stock-api:8081/candles/AAPL?days=60'`.
- **Reproduction:** `curl localhost:8082/features/features/AAPL`.
- **Suspected cause:** `routes_features.py` builds the upstream URL as
  `f"{svc.config.stock_api_url.rstrip('/')}/candles/{symbol}"` with no
  `/stock` segment. `VINU_STOCK_API_URL=http://stock-api:8081` is the
  service root; stock-api mounts its routes under `/stock`, so the real
  path is `/stock/candles/AAPL`. Same bug class as vinu-news Bug-2
  (which was fixed in vinu-news and vinu-initial-analysis) — this inline
  call in vinu-tools was missed.
- **Severity:** major (even the reachable route can't return data).

### Bug-4 — parametrized kind lookup (`rsi_14`) returns 422

- **Found during:** post-fix route sweep of `GET /features/{symbol_or_kind}`
  after Bug-2/3 were fixed.
- **Date:** 2026-07-31
- **Symptom:** `GET /features/rsi_14` → HTTP 422
  `{"detail":"Unknown indicator kind: rsi_14"}`. Plain kind works
  (`GET /features/rsi` → 200). The indicator examples advertise
  parametrized forms (`examples: ["rsi", "rsi:period=20", "rsi_14"]`),
  so `rsi_14` is part of the documented contract.
- **Reproduction:** `curl localhost:8082/features/rsi_14`.
- **Suspected cause:** in the `is_known` branch of `get_feature_or_symbol`
  (routes_features.py), when `get_indicator("rsi_14")` raises, the code
  resolves the base kind via prefix and rebuilds `meta`, but then calls
  `format_help(symbol_or_kind)` with the original `"rsi_14"` string.
  `format_help` → `get_indicator("rsi_14")` raises `ValueError`, which
  `vinu_lib.server`'s `ValueError` handler maps to 422. Pre-existing
  (identical logic in the old double-prefixed route), surfaced by the
  post-fix sweep.
- **Severity:** low.

### Bug-5 — manifest.md reports `Status: running` for completed runs

- **Found during:** checklist "manifest.md per run accurately describes
  what was computed" — after the first real run (request 1) completed.
- **Date:** 2026-07-31
- **Symptom:** `data/runs/1_e2e_basic_ta_2022_2026/manifest.md` shows
  `**Status:** running` even though `GET /requests/1` reports
  `status: "done"` with 3374 rows. A stale pre-existing manifest
  (`pipeline-run-JPM`, 2026-07-23) shows the same `Status: running`.
- **Reproduction:** run any request, then inspect its `manifest.md`.
- **Suspected cause:** `engine.process()` calls `write_manifest(...)`
  using `request.status` *while* the worker has already marked the row
  `running`; the worker only calls `mark_done()` after `process()`
  returns. So the manifest is always written with `status=running`.
  `write_manifest` (`vinu_tools/engine/manifest.py`) has no way to know
  the final status.
- **Severity:** low (cosmetic/inaccurate audit line; the API status is
  authoritative).

### Bug-6 — request for symbols with no cached data silently "done", manifest references missing parquet

- **Found during:** checklist "Behavior when `vinu-stock-price` has
  partial or missing data" — a request for a non-cataloged symbol
  (SPDR).
- **Date:** 2026-07-31
- **Symptom:** `POST /requests` with `symbols:["SPDR"]` (no stock-price
  data) → `status: "done"`, `row_count: 0`, `file_path` set. The run
  dir contains **only** `manifest.md` — `engine.process()` deletes the
  empty `features.parquet` when `total_rows == 0`, but the manifest
  still says `**File:** features.parquet`. Callers get a silent empty
  result with no indication the upstream data is missing.
- **Reproduction:** submit the SPDR request above, then
  `ls /data/runs/3_e2e_missing_symbol/`.
- **Suspected cause:** `vinu_tools/engine/engine.py` writes an empty
  parquet, then unlinks it when `total_rows == 0`, then
  `write_manifest` still records `features.parquet`; the worker
  `_execute` marks the run `done` regardless of row count. Partial
  coverage is handled well (mixed request AAPL+SK → `done`, 20 rows,
  SK skipped) — only the all-empty case is silent.
- **Severity:** medium (violates the "clear status, not a silent wrong
  result" expectation for missing upstream data).

### Fixed-6

- **Root cause:** confirmed via repro — `worker._execute` called
  `mark_done` regardless of `row_count`; `engine.process` had already
  deleted the empty parquet, leaving only a manifest that still
  references `features.parquet`.
- **Fix applied:** `vinu_tools/worker/runner.py` `_execute` now raises
  `ValueError("No candle data returned for any requested symbol in the
  given range")` when `row_count == 0`. This routes through the
  worker's existing exception handler, which removes the run dir and
  calls `mark_failed` → the request reports `failed` with a clear
  `error_message`.
- **Verification:** all-missing request (SPDR) → `status: failed`,
  `error_message: "No candle data returned for any requested symbol in
  the given range"`, `file_path: null`. Mixed request (AAPL+SK) →
  `status: done`, 20 rows, SK skipped (partial coverage still graceful).
  features-api healthy after rebuild.
- **Status:** fixed.

### Fixed-5

- **Root cause:** confirmed via repro — `engine.process()` calls
  `write_manifest()` with `request.status`, which the worker set to
  `running` before processing and only flips to `done` (via
  `mark_done()`) after `process()` returns. Manifest is therefore always
  written with `status=running`. Since a failed run's directory is
  removed by the worker's exception handler, any surviving manifest
  always describes a completed run.
- **Fix applied:** `write_manifest` gains a `status` param
  (`vinu_tools/engine/manifest.py`); `engine.process()` passes
  `status=STATUS_DONE` (`vinu_tools/engine/engine.py`).
- **Verification:** new run `2_e2e_manifest_check` (trend_pack, AAPL,
  120d) → manifest shows `**Status:** done`, Rows 81, correct symbols /
  features / ts range. features-api healthy after rebuild.
- **Status:** fixed.

### Fixed-2

- **Root cause:** confirmed via repro above — `vinu_tools/server/routes_features.py`
  defined `@router.get("/features")` and `@router.get("/features/{symbol_or_kind}")`
  while `app.py` mounts the merged router under `route_prefix="features"`,
  so the real paths were `/features/features` and `/features/features/{symbol_or_kind}`.
  Same bug class as vinu-news Bug-4.
- **Fix applied:** `routes_features.py` — removed the embedded `/features`
  prefix from both routes (`@router.get("/features")` → `@router.get("/catalog")`,
  `@router.get("/features/{symbol_or_kind}")` → `@router.get("/{symbol_or_kind}")`).
  The `/{symbol_or_kind}` catch-all is now registered LAST (after `/factors*`
  and `/ml/models`) so it can't shadow them. Note: FastAPI ≥0.141 rejects an
  empty-path route (`@router.get("")`) when the router is included into a
  prefix-less merged router (`Prefix and path cannot be both empty`), so the
  catalog route uses the explicit `/catalog` path (public
  `/features/catalog`; nothing in the plan/consumers used the old
  `/features/features` catalog URL).
- **Cross-component fix (vinu-research, same root cause):**
  `vinu_research/tools.py:215` called `get(f"/features/{symbol}")` on a
  client whose base already appends `/features` — the double-append only
  "worked" because the route was wrongly double-prefixed. Changed the call
  path to `get(f"/{symbol}")`, matching the prefix-once convention its own
  simulator/stock/correlation clients use.
- **Verification:** `docker compose up -d --build features-api research-api`
  → both healthy. `GET /features/AAPL?indicators=sma_20,rsi_14` → 200
  `{"symbol":"AAPL","values":{"sma_20":297.57,"rsi_14":46.93}}`.
  Old `/features/features/AAPL` → 404 (gone). `/features/factors`,
  `/features/presets`, `/features/requests`, `/features/health`,
  `/features/ml/models` all 200; `/features/catalog` → 24 indicators.
- **Status:** fixed.

### Fixed-3

- **Root cause:** confirmed via repro above — the inline stock fetch in
  `get_feature_or_symbol` built `f"{stock_api_url}/candles/{symbol}"` with
  no `/stock` segment. `VINU_STOCK_API_URL=http://stock-api:8081` is the
  service root; stock-api mounts under `/stock`. Same bug class as
  vinu-news Bug-2 (fixed there and in vinu-initial-analysis); this inline
  call in vinu-tools was missed in that earlier pass.
- **Fix applied:** `routes_features.py` → url is now
  `f"{stock_api_url.rstrip('/')}/stock/candles/{symbol}"`.
- **Verification:** same 200 repro as Fixed-2 (real `sma_20`/`rsi_14`
  values returned from stock-api data). `features-api` healthy after rebuild.
- **Status:** fixed.

### Fixed-4

- **Root cause:** confirmed via repro — in the `is_known` branch,
  `get_indicator("rsi_14")` raises, the prefix is resolved back to the
  base kind, but `format_help(symbol_or_kind)` was called with the original
  `"rsi_14"`, which raises again → `vinu_lib`'s ValueError handler → 422.
- **Fix applied:** `routes_features.py` → `out.help_text = format_help(meta.kind)`
  (the resolved canonical kind) instead of `format_help(symbol_or_kind)`.
- **Verification:** `GET /features/rsi_14` → 200 with full meta +
  help_text; `GET /features/sma_20` → 200; plain `GET /features/rsi` → 200.
  features-api healthy after rebuild.
- **Status:** fixed.
