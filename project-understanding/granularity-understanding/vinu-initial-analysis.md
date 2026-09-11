# vinu-initial-analysis

## What it is

Runs every quantitative "angle" (forecasting model, statistical test,
structural analysis) for a symbol and stores each one's output. This IS
the "28 analyses" layer the user named — confirmed count: **28** angle
subpackages under `vinu_initial_analysis/angles/` (each its own folder
with a `compute.py`; a 29th filesystem entry, `__pycache__`, isn't an
angle). It does NOT synthesize them into a single LLM narrative itself —
that's `vinu-research`'s Summary Agent, downstream.

## Trigger / cadence

Two independent loops, same `serve`/`compute` process split as
`vinu-stock-price`:

1. **Compute worker** (`vinu-initial-analysis compute --continuous
   --interval=3600`, `cli.py::compute_main`): a `while True` loop,
   default **1 hour** between cycles (`--interval` default 3600s).
2. **HTTP API** (`serve_main`, FastAPI): always up, answers reads and
   on-demand trigger requests.

## Pipeline

**Each compute cycle** (`cli.py::compute_main`'s loop body):
1. `_resolve_tickers()` — re-fetches the watchlist from
   `GET {stock_api_url}/stock/watchlist/tickers` fresh every cycle (not
   cached at startup), so a ticker added mid-run is picked up without a
   restart. Falls back to a hardcoded 7-mega-cap list
   (`AAPL/MSFT/GOOGL/AMZN/META/TSLA/NVDA`) if the watchlist is empty or
   unreachable — a known, documented survivorship-bias limitation, not an
   oversight.
2. For each ticker, `_compute_batch` → `runner.run(symbol, from_ts, to_ts)`
   (`runner.py::AngleRunner.run`) — **this is the actual "28 analyses"
   step**:
   - Window: `from_ts` = `config.stage1_start_date`, `to_ts` = the last
     *completed* calendar period end (`last_completed_period_end`,
     quarterly by default via `tier2_period_months`) — deliberately NOT
     `now`, so the same window is reused across cycles until a new
     quarter closes and the run-dedup cache (`RunLog.has_existing_run`)
     can actually skip redundant recomputation instead of defeating
     itself every cycle.
   - `AngleRunner._discover()` (run once at construction) walked
     `angles/` and found every subfolder with a `compute.py` — 28 of
     them, sorted alphabetically (arima, backtesting_44_metrics, chronos,
     dlinear, drawdown_deep_dive, exponential_smoothing, garch,
     itransformer, kalman_filters, kronos, lag_llama, lpatchtst, lstm,
     moirai, moment, news_price_causality, patchtst,
     peer_relative_strength, pnl_attribution, regime_analysis,
     shock_clustering, shock_personality, tft, timer_timerxl, timesfm,
     tips_regime_aware_transformer, trend_lifecycle,
     trend_session_structure).
   - `runner.run()` loops these **sequentially, in-process**, one angle
     at a time (not parallel, unlike `vinu-stock-price`'s per-symbol
     ingest). Each angle is individually wrapped in try/except — one
     angle failing (a model erroring, missing dependency data) never
     stops the rest of the suite, and the failure is still recorded in
     `RunLog` with its own `run_id`, not silently dropped.
   - Each angle's own `compute.py::compute(...)` runs its actual
     model/statistic (an ARIMA fit, a GARCH volatility estimate, an LSTM
     forecast, a Kalman filter, a Granger-causality test against news,
     shock-clustering correlation, etc.) against price data pulled via
     `PriceClient` (this service's own client hitting
     `vinu-stock-price`'s `/stock/candles/...`) and, for the
     news-dependent angles, `NewsClient` hitting `vinu-news`.
   - Each angle's result is written to `AngleStorage` (parquet, one file
     per angle/symbol/granularity) and logged to `RunLog` (SQLite —
     `RunLog.record_run`, real run_id, elapsed time, tier, success/failure).
   - `"skipped_existing"` vs `"completed"` is the return status per
     angle: a cache hit (this exact symbol/angle/timeframe/window already
     has a completed run) reports `skipped_existing` distinctly from a
     freshly computed `completed` result — never conflated.
3. That's it per cycle — "then finish it" is exactly this: 28 angles run,
   each writes its own parquet + RunLog row, and the cycle sleeps until
   the next hour.

**"Then move to summary"**: this service does NOT do that step itself.
`GET /analysis/story/{ticker}` (`service.py::get_story`) is the closest
thing here — it aggregates the *latest* result from every angle into one
combined read, still raw per-angle data, no LLM synthesis. The actual
narrative synthesis (turning 28 angles' worth of numbers into a written
thesis) is `vinu-research`'s Summary Agent / `angle_synthesizer` (see
`vinu-research.md` once written, and
`project-understanding/04-new-full-explanation-v2.md`'s "1. Summary
Agent" section for the existing high-level description) — it reads this
service's angle outputs over HTTP, this service never calls out to an LLM
itself.

**On-demand / ad-hoc runs** (`POST /analysis/run/{ticker}`,
`server/routes_read.py:112`): lets a caller trigger a subset of angles
(`angle_names`) outside the hourly cycle — e.g. Phase 7's feedback loop
refreshing just `shock_personality`/`shock_clustering` for one symbol
without re-running all 28. Runs as a background job
(`GET /analysis/run/jobs/{job_id}` polls status), tier="tier3" (ad-hoc,
prunable, distinct from the scheduled tier2 runs).

## Storage

- Parquet, one file per angle × symbol × granularity
  (`storage/parquet.py::AngleStorage`).
- `RunLog` (SQLite, `storage/meta.py`) — every run attempt (success or
  failure), real run_id, elapsed time, tier, the window computed.
- `storage/factsheet.py` — a derived, pre-formatted per-angle "factsheet"
  view (`GET /analysis/factsheet/{ticker}/{method}` in the v1 API), used
  for a quick human-readable summary of one angle's own output — still
  per-angle, not cross-angle synthesis.

## Talks to

- **Outbound**: `vinu-stock-price` (`PriceClient` — historical candles
  every angle needs), `vinu-news` (`NewsClient` — the news-dependent
  angles: `news_price_causality`, novelty/impact scoring).
- **Inbound**: `vinu-research`'s Summary Agent reads per-angle results
  (`GET /analysis/angle/{angle_name}/{ticker}`, `GET /analysis/story/{ticker}`)
  to build its synthesized thesis; `vinu-live`'s orchestrator reads
  `shock_clustering`/`shock_personality` specifically for its shock-batch
  prioritization (`_fetch_shock_cluster_correlation`/
  `_fetch_shock_personality_score` in `vinu-live/trade_plan/orchestrator.py`).
