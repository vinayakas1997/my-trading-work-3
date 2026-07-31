# vinu-simulator — Test Log

**Status:** Not started

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
