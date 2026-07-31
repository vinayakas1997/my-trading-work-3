---
name: vinu-simulator
port: 8085
depends_on: [vinu-strategy, vinu-stock-price]
---

# vinu-simulator

## What it does

Backtest engine — replays a strategy's weights against historical price
data, producing P&L, trades, equity curve, and performance metrics.

## Scope for this E2E plan

Runs each of the three strategies' weights against real price data for
2022-01-01 → 2026-06-30, producing Sharpe, max drawdown, win rate, Calmar
ratio, and total/annualized return, compared against equal-weight and
buy-and-hold (SPY/QQQ) baselines. This is the core Stage 1 deliverable —
the numbers this service produces are what the go/no-go decision for Stage
2 will be based on.

Note: this service-level simulator is distinct from (and predates)
`vinu-portfolio`'s own `historical_simulation.py` module (built during the
Step 07 audit work) — that module reuses `vinu-portfolio`'s
`allocate_risk_parity()` directly rather than calling this service. Both
exist; this plan uses `vinu-simulator`'s service API for per-strategy
backtests and `vinu-portfolio`'s CLI for the unified multi-strategy
allocation replay.

## When it runs

Depends on `vinu-strategy` and `vinu-stock-price` (docker-compose
`depends_on: strategy-api, stock-api`). Runs after strategies have
evaluated weights.

## Where data is stored

- Results (equity curve, trades, metrics): via `vinu_simulator/storage/results.py`.
- Run metadata: via `vinu_simulator/storage/meta.py` (SQLite), under
  `VINU_SIMULATOR_DATA_ROOT` (default `./data`).

## Dependencies

- `VINU_STRATEGY_API_URL` (`vinu-strategy`, port 8084)
- `VINU_STOCK_API_URL` (`vinu-stock-price`, port 8081)
- `VINU_FEATURES_API_URL` (`vinu-tools`, port 8082)

## Configuration relevant to this plan

- `initial_capital`, `transaction_cost_pct`, `slippage_pct` — must be set
  to realistic values before Stage 1, not left at defaults, since these
  directly affect the Sharpe/drawdown numbers the go/no-go decision relies
  on.
- `benchmark_tickers` (default SPY, QQQ) — the baseline comparison.

## API surface used by this plan

- `POST /simulate` — run a backtest for a strategy over the date range.
- `GET /results/{run_id}/metrics` — retrieve performance metrics.
- `GET /results/{run_id}/equity` — equity curve for charting/review.

## Known gap as of this document

No run has ever been executed against real data — only synthetic-data unit
tests exist so far (`vinu-portfolio/tests/test_historical_simulation.py`).
