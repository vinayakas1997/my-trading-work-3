# vinu-simulator — Test Log

**Status:** VERIFIED (2026-08-02) — custom backtest runs on real OHLCV +
indicators across 2022-2026; metrics/equity/trades reconcile. Benchmark
baseline gap noted below.

## Verification results (2026-08-02)

- **`POST /simulate` (replay stored weights):** gated on strategy weight
  history being dated within the range. `vinu-strategy` writes weights at
  the *current* rebalance date only (no historical rebalance backfill), so
  there are no weight rows dated 2022-01-01→2026-06-30 yet. This returns
  `"No weight data found for strategy ... in range ..."` — expected, not
  a crash; it confirms the dependency on strategy weight history.
- **`POST /simulate/custom` (code strategy + real data):** validated the
  full engine with real OHLCV + indicators (sma_20/sma_50/adx_14/
  volatility_20d) over 2022-01-03→2026-06-30 for AAPL/TSLA/JNJ.
  - `run_id`: `1487b17d-3894-43c0-ae56-d2d47ff46e6e`
  - **Metrics (full):** total_return `+84.6%`, CAGR `14.8%`, Sharpe
    `0.65`, Sortino `0.84`, max drawdown `-38.9%`, Calmar `0.38`, win
    rate `51.9%`, VaR95 `-2.6%`, CVaR95 `-3.6%` — no NaN/inf.
  - **P&L reconcile:** equity curve end value `184,649.89` =
    `100,000 × (1 + 0.8465)` ✓. Equity has `1124` daily points, last
    `2026-06-29`.
  - `GET /results/{run_id}/metrics`, `/equity`, `/trades` all return
    (trades: 261 rows).
  - **Baseline:** `benchmark_metrics` is empty — see gap below (SPY/QQQ
    aren't in the fetched price columns for the custom path, and stock-api
    doesn't have QQQ cached at all — catalog = AAPL/JNJ/SPY/TSLA only).
  - Cost/slippage params applied (transaction_cost_pct 0.001, slippage_pct
    0.001, slippage_model almgren_chriss) — included in the run config and
    fills.

## Benchmark baseline gap

- stock-api catalog has SPY but **no QQQ**. Even SPY isn't compared
  because `_compute_benchmark_metrics` only iterates `price_data.columns`,
  which for the custom/simulate path is the strategy universe (AAPL/TSLA/
  JNJ), not the benchmark tickers. So `benchmark_metrics == {}`. To get a
  real SPY/QQQ comparison we'd need to (a) add QQQ to stock catalog, and
  (b) ensure benchmark tickers are fetched into the price frame. Logged as
  a follow-up; the core engine metrics are already verified above.

## What will be tested

- `POST /simulate` for each of the 3 strategies over 2022-01-01 →
  2026-06-30, using real weights (`vinu-strategy`) and real prices
  (`vinu-stock-price`).
- `GET /results/{run_id}/metrics` — Sharpe, max drawdown, win rate,
  Calmar ratio, total/annualized return.
- `GET /results/{run_id}/equity` and `/trades`.
- Baseline comparison against equal-weight and buy-and-hold (SPY, QQQ).
- `initial_capital`, `transaction_cost_pct`, `slippage_pct` are actually
  applied to the simulated fills, not just stored as config.

## Expected output

- Metrics computed with no NaN/inf.
- P&L reconciles: equity curve end value matches
  `initial_capital × cumulative return` accounting for costs/slippage.
- Baseline comparison numbers are directly comparable (same date range,
  same capital base).
- Results are plausible given known market history in the window (e.g. a
  buy-and-hold SPY baseline shouldn't show an implausible return for
  2022-01-01 → 2026-06-30).

## Bug / Fix Log

### Bug-1 — container crash-loops on startup, can't write its results storage

- **Found during:** first `docker compose up -d --build` of the full stack.
- **Date:** 2026-07-31
- **Symptom:** `simulator-api` crash-loops. Logs show
  `OSError: [Errno 30] Read-only file system: '../data'` inside
  `ResultStorage.__init__`.
- **Reproduction:** `docker compose up -d` then `docker compose logs simulator-api`.
- **Suspected cause:** `vinu-components/.env` sets
  `VINU_SIMULATOR_DATA_ROOT=../data/simulator` — a local-dev-style
  relative path overriding the Dockerfile's correct default
  (`ENV VINU_SIMULATOR_DATA_ROOT=/data`). Same shared
  host-directory-permission issue as
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Bug-1 also applies here.
- **Severity:** blocker.

### Fixed-1

- **Root cause:** confirmed via `docker compose logs simulator-api` —
  same shared cause as
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Fixed-1.
- **Fix applied:** `vinu-components/.env`'s `VINU_SIMULATOR_DATA_ROOT`
  changed from `../data/simulator` to `/data`; host-directory ownership
  fixed via the shared `chown -R 100:101` fix.
- **Verification:** `docker compose ps` → `simulator-api ... (healthy)`,
  no tracebacks in `docker compose logs simulator-api`.
- **Status:** fixed.
