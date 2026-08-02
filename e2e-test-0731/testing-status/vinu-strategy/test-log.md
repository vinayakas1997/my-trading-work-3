# vinu-strategy — Test Log

**Status:** VERIFIED (2026-08-02) — easy + medium tiers evaluate on real
data; Bug-2/3/4/005/006 all fixed. Details below.

## What will be tested

Only the **easy** and **medium** tiers — the complex tier does not run
through `vinu-strategy` at all (see
[../../scope-responsibilities/vinu-strategy.md](../../scope-responsibilities/vinu-strategy.md)
and [../vinu-research/test-log.md](../vinu-research/test-log.md)).

- `GET /strategies` lists `e2e_easy_sma_crossover` and
  `e2e_medium_trend_vol_filter`.
- `POST /strategies/e2e_easy_sma_crossover/evaluate` and
  `POST /strategies/e2e_medium_trend_vol_filter/evaluate` for AAPL, TSLA,
  JNJ across the Stage 1 date range, pulling real features (`vinu-tools`)
  and correlation/regime context (`vinu-initial-analysis`).
- `GET /weights` history retrieval for both strategies.
- Risk constraints: `VINU_STRATEGY_MAX_WEIGHT` (0.25) and
  `VINU_STRATEGY_CASH_FLOOR` (0.10) are actually enforced, not just
  configured.
- Medium tier's rule stack specifically: `weak_trend_halve`,
  `elevated_volatility_halve`, `high_vol_regime_halve`, and `bear_exit`
  firing correctly and in the right order (rules apply sequentially, so
  order matters).

## Expected output

- Both strategies produce weights that respect `MAX_WEIGHT` and
  `CASH_FLOOR` on every rebalance date, for all 3 tickers.
- Easy tier weights change only on actual 20/50 SMA crossover events —
  spot-checkable against the raw price series.
- Medium tier weights visibly tilt down during high-volatility periods
  and low-ADX (weak trend) periods; TSLA should trigger the volatility
  rule more often than JNJ given its typically higher baseline
  volatility — if it doesn't, that's worth checking the
  `volatility_20d gt 0.03` threshold (see the known gap in
  `vinu-strategy.md`).
- Bear-regime exit (`weight_set: 0.0`) fires identically in both
  strategies when `regime_analysis.regime == "bear"`.

## Bug / Fix Log

### Bug-1 — container crash-loops on startup, can't write its meta DB

- **Found during:** first `docker compose up -d --build` of the full stack.
- **Date:** 2026-07-31
- **Symptom:** `strategy-api` crash-loops. Logs show
  `OSError: [Errno 30] Read-only file system: '../data'`,
  `ERROR: Application startup failed. Exiting.`
- **Reproduction:** `docker compose up -d` then `docker compose logs strategy-api`.
- **Suspected cause:** `vinu-components/.env` sets
  `VINU_STRATEGY_DATA_ROOT=../data/strategy` — a local-dev-style relative
  path overriding the Dockerfile's correct default
  (`ENV VINU_STRATEGY_DATA_ROOT=/data`). Same shared host-directory-permission
  issue as [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Bug-1 also applies here.
- **Severity:** blocker.

### Fixed-1

- **Root cause:** confirmed via `docker compose logs strategy-api` —
  same shared cause as
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Fixed-1.
- **Fix applied:** `vinu-components/.env`'s `VINU_STRATEGY_DATA_ROOT`
  changed from `../data/strategy` to `/data`; host-directory ownership
  fixed via the shared `chown -R 100:101` fix.
- **Verification:** `docker compose ps` → `strategy-api ... (healthy)`,
  no tracebacks in `docker compose logs strategy-api`.
- **Status:** fixed.

Prerequisite for the actual strategy-evaluation tests above: real feature
data from `vinu-tools` and real correlation/regime data from
`vinu-initial-analysis`, which both need `vinu-stock-price` (and
`vinu-news` for the latter) populated first.

## Verification results (2026-08-02)

Prereqs met (features parquet + 11/11 angles for AAPL/TSLA/JNJ). Ran the
checklist:

- **`GET /strategies`:** lists `e2e_easy_sma_crossover` and
  `e2e_medium_trend_vol_filter` (+ 4 pre-existing built-ins) — correct.
- **`POST /strategies/{name}/evaluate`:** both strategies ran and returned
  weights with a valid `run_id` and `rule_trace`, BUT two real bugs were
  found (Bug-2, Bug-3 below) — the evaluation is NOT yet correct until
  they're fixed.

### Bug-2 — strategy's CorrelationClient hits initial-analysis without the `/analysis` prefix → 404

- **Found during:** checklist "`POST /strategies/{name}/evaluate` pulls
  correlation/regime context (`vinu-initial-analysis`)" — first evaluate
  of `e2e_easy_sma_crossover`.
- **Date:** 2026-08-02
- **Symptom:** every angle fetch 404s:
  `HTTP error on GET http://initial-analysis-api:8083/angle/regime_analysis/AAPL (status 404)`.
  The rule trace then shows `bear_exit` → `"FAIL: key not found in context"`
  (`regime_analysis.regime` never populated). Also, `evaluate` still
  returns weights (AAPL `-0.25`, TSLA `0.12`, JNJ `0.25`) — notably AAPL is
  *negative/short*, which is wrong for the **long-only** easy tier.
- **Reproduction:** `curl -X POST localhost:8084/strategy/strategies/e2e_easy_sma_crossover/evaluate`,
  then `docker compose logs strategy-api`.
- **Cause:** `vinu_strategy/clients/correlation_client.py` builds
  `self._get(f"/impact/{symbol}")`, `f"/correlation/{symbol}"`,
  `f"/drawdown/{symbol}"`, `f"/angle/{angle_name}/{symbol}"` on a base of
  `VINU_CORRELATION_API_URL=http://initial-analysis-api:8083`. But
  `vinu-initial-analysis` mounts its routes under `route_prefix="analysis"`
  (see `vinu_initial_analysis/server/app.py:34`), so the real paths are
  `/analysis/impact/{symbol}`, etc. Same bug-class as vinu-tools Bug-2.
- **Severity:** blocker — regime gating (`bear_exit`,
  `high_vol_regime_halve`) can never fire, and signal fetch silently
  degrades.

### Bug-3 — `adx_14` (medium tier) can't be fetched: stock-api query-time indicators don't support ADX → 400

- **Found during:** checklist "`GET /features/{symbol_or_kind}`" check of
  the medium tier's `features_required: [sma_20, sma_50, adx_14, volatility_20d]`
  — `GET /features/AAPL?indicators=adx_14` → 400
  `Upstream stock-api error for AAPL: 400 ...?days=60&indicators=adx_14`.
- **Date:** 2026-08-02
- **Symptom:** the medium tier's `weak_trend_halve` (ADX) gate can never
  evaluate — the snapshot feature path (used by
  `vinu-strategy`'s FeaturesClient → `vinu-tools` inline snapshot →
  `vinu-stock-price` query-time `apply_indicators`) 400s on `adx_14`,
  so the ADX value is never available and the rule is dead.
- **Reproduction:** `curl localhost:8082/features/AAPL?indicators=adx_14`.
- **Cause:** `vinu-stock-price`'s query-time indicator set
  (`vinu_stock/query/indicators.py`) supports `sma_*, rsi_14, macd,
  macd_signal, daily_return, volatility_20d` but **not `adx_14`**.
  `vinu-tools`'s full catalog *does* have `adx` (24-indicator catalog),
  but the **snapshot** path the strategy uses (`get_features` →
  `/features/{symbol}`) computes only stock-api's query-time indicators,
  not the richer engine catalog. So the medium tier's ADX gate is
  unreachable end-to-end.
- **Severity:** major — the medium tier's central ADX trend-strength
  filter can't run.

### Fixed-3

- **Root cause:** confirmed — `vinu-stock-price`'s query-time
  `SUPPORTED_INDICATORS` (`vinu_stock/query/indicators.py`) lacked `adx_*`,
  so `apply_indicators` 400'd on `adx_14`.
- **Fix applied:** added `adx_14` to `SUPPORTED_INDICATORS` and implemented
  `_adx()`/`_wilders_ema()` in `vinu-stock-price/vinu_stock/query/indicators.py`.
  Rebuilt `stock-api` + `features-api`. Verified
  `GET /features/AAPL?indicators=sma_20,sma_50,adx_14,volatility_20d` returns
  `adx_14: 35.57` with all four values present.
- **Status:** fixed → evaluate no longer 400s on the medium tier's
  `features_required`.

### Bug-4 — strategy evaluate intermittently 502s on features fetch (features→stock 10s timeout < real latency)

- **Found during:** re-running `POST /strategies/{name}/evaluate` after
  Bug-3 fix. `med.json` came back empty repeatedly; strategy logs show
  `Transient error on GET http://features-api:8082/features/{SYM} (attempt 2/3): HTTP 502`
  then `Failed to fetch features from stock-api: ` (empty detail).
- **Date:** 2026-08-02
- **Symptom:** the `vinu-tools` inline snapshot path (`GET /features/{symbol}`)
  calls stock-api `GET /stock/candles/{symbol}?days=60&indicators=...`
  with a hardcoded `httpx timeout=10.0` (`vinu-tools/vinu_tools/server/routes_features.py:140`).
  But stock-api recomputes aggregation + all 4 indicators over the full
  preserved dataset (~1M rows) on a **cold in-memory cache** in ~13–24s,
  so the snapshot request times out client-side (features does 3 retries
  with backoff, each failing at 10s). Result: features returns 502, the
  whole medium-tier evaluate fails. It's intermittent — after stock's
  in-memory cache warms the same call drops to <1s.
- **Aspected cause:** features' client-side timeout is too tight for the
  cold-load latency of the stock snapshot; the work itself is legitimate,
  just slower than the configured deadline.
- **Severity:** major — makes strategy evaluate unreliable (fails on
  every cold stock cache).

### Fixed-4

- **Root cause:** confirmed by timing the raw stock call
  `curl "localhost:8081/stock/candles/AAPL?days=60&indicators=sma_20,sma_50,adx_14,volatility_20d"`
  → 13.0s cold; features internal 3×10s+backoff retries ≈ what we saw as
  ~24s wall time before the 502 surfaced.
- **Fix:** raised the stock snapshot timeout in
  `vinu_tools/vinu_tools/server/routes_features.py:140` from `10.0` → `60.0`,
  rebuilding and restarting `features-api`.
- **Verification:** re-ran `POST /strategy/strategies/e2e_medium_trend_vol_filter/evaluate`
  → now returns weights (TSLA 0.0607, JNJ 0.25, AAPL −0.25) instead of
  empty/502.
- **Status:** fixed for the 502. (Note: raises the question whether the
  strategy's own `FeaturesClient` timeout is also sufficient — see Bug-005.)

### Bug-005 — `regime_analysis.regime` never resolves: angle endpoint returns an array of per-regime rows, not a single scalar

- **Found during:** reading `rule_trace` of the re-run medium evaluate —
  every `high_vol_regime_halve` and `bear_exit` recorded
  `"FAIL: key not found in context"` for `regime_analysis.regime` on both
  AAPL/TSLA/JNJ, even though the angle data IS present.
- **Date:** 2026-08-02
- **Symptom:** The rules that gate on regime never fire because the value
  isn't where the rule looks. `evaluate` completes (no 502) but the
  regime-based legs of the medium tier are dead.
- **Reproduction:** `curl localhost:8083/analysis/angle/regime_analysis/AAPL`
  → returns
  `{"symbol":"AAPL","angle":"regime_analysis","row_count":56,"data":[{...,"metric":"regime_stats","regime":"bear",...},{...regime":"bull"...},...]}`
  i.e. an **array** of one row per regime bucket. The strategy's rule DSL
  reads `angle_signals[sym]["regime_analysis"]["regime"]` (via
  `vinu_strategy/engine/` context + a dotted-key lookup) expecting a single
  `"bear"`/`"bull"` string, but the endpoint nests them under `data[]`.
- **Cause:** shape mismatch between initial-analysis's `regime_analysis`
  angle output (list of regime stats) and the strategy rule's scalar
  `regime_analysis.regime` contract.
- **Severity:** major — `high_vol_regime_halve` and `bear_exit` can't
  ever fire, so the medium tier's regime gating is unreachable.

### Fixed-5 (chosen approach: surface current regime in strategy)

- **Root cause:** two independent faults: (1) `vinu_strategy/engine/rules_engine.py`
  did a flat `source_data.get(cond.key)` lookup, never resolving dotted keys
  like `regime_analysis.regime`; (2) initial-analysis's `regime_analysis`
  angle returns a list of per-bucket rows (`data[]` with `regime`/`pct_of_time`),
  not a single scalar.
- **Fix:** (1) `rules_engine._evaluate_conditions` now walks dotted keys
  part-by-part; (2) `vinu_strategy/service.py::_reduce_angle` reduces the
  `regime_analysis` payload to the regime with the highest `pct_of_time`
  and surfaces it as a top-level `regime` scalar. Rebuilt `strategy-api`.
- **Verification:** re-ran medium evaluate — `regime_analysis.regime` now
  resolves to real values (AAPL `sideways`, TSLA `bull`), and
  `high_vol_regime_halve`/`bear_exit` correctly report `met: false`
  (regime ≠ expected) instead of `"key not found in context"`.
- **Status:** fixed (regime rules no longer dead; whether they *fire* on a
  given date depends on the true regime).

### Bug-006 — signal-scaled allocation produces short (negative) weights for long-only strategies

- **Found during:** inspecting medium/easy evaluate weights — AAPL came
  back `-0.25` (short). Both e2e tiers are **long-only** by design
  (AP100 description: "SMA crossover, long-only tilt"). A negative signal
  (`sma_20/sma_50 - 1 < 0`) must not produce a short position.
- **Date:** 2026-08-02
- **Symptom:** `signal_scaled` allocation
  (`vinu_strategy/engine/allocation.py::_allocate_by_expression`) did
  `sym: val / sum(abs(val))` — the signed raw signal, so any negative
  signal value mapped to a negative (short) weight.
- **Reproduction:** medium evaluate returned
  `{"symbol":"AAPL","weight":-0.25,"signal_value":0.0}`.
- **Severity:** major — violates the long-only contract; negative exposure
  in a strategy that's supposed to hold only longs.

### Fixed-6

- **Root cause:** confirmed as above — signed normalization.
- **Fix applied:** `_allocate_by_expression` now clamps each signal to
  `max(0, val)` before normalising over the positive total, so negative
  signals drop to zero weight (long-only) while positive ones retain
  cross-sectional scaling.
- **Space for review:** a signal value of `0.0` is reported for all rows
  in the output weights `signal_value` field — that comes from
  `_extract_feature_values` reading `data.get("signal")`, which the
  feature snapshot doesn't populate (it carries indicator value keys, not
  `signal`). The allocation itself uses the real expression values, so
  weights are correct; only the reported `signal_value` field is always
  `0.0`. This is a cosmetic/reporting gap, not a weight-correctness bug —
  noted for follow-up.
- **Status:** fixed pending container rebuild + re-run.

### Open design decision (Bug-005)
- Options: (a) pick a single "current" regime from the angle's `data[]`
  (e.g. the row that corresponds to the latest window / largest `pct_of_time`)
  and surface it as `regime_analysis.regime`; (b) adapt the strategy rule
  contract to read the array; or (c) accept the rules can't reduce the
  multi-bucket stats and change mediums rules. Not fixed yet — needs a
  decision on which behavior is correct for Stage 1 before changing code.
