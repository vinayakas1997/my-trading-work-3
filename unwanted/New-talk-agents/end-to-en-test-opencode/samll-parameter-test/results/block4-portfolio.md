# Block 4 — Portfolio

Cross-service smoke: portfolio build + evaluate.

Run date: 2026-08-11. Endpoints are read-only portfolio views; build/evaluate
are exposed as `/portfolio/state`, `/portfolio/daily-allocation`,
`/portfolio/risk/status` (no separate build/evaluate POST in this service).

## Build / state
- Endpoint: `GET /portfolio/state`, `GET /portfolio/weights`, `GET /portfolio/strategies`
- Expected: portfolio with holdings/weights

| Run | Status | Holdings count | Detail |
|---|---|---|---|
| portfolio state | PASS (0.75s) | 6 strategies | keys: status, timestamp, n_strategies, strategies, weights, correlation_matrix, shock_correlation |
| strategies list | PASS (0.04s) | 6 strategies | adx_filtered_crossover, e2e_easy_sma_crossover, e2e_medium_trend_vol_filter, ma_crossover, news_aware_momentum, rsi_mean_reversion |
| weights | PASS (0.06s) | 6 weights | target_weight 0.1667 each (equal split) |
| daily-allocation | PASS (0.66s) | 6 strategies | includes regime + account_equity |
| AAPL / TSLA separate | n/a | n/a | portfolio is strategy-based, not ticker-based |

## Evaluate / risk
- Expected: evaluation metrics (return, risk, etc.)

| Run | Status | Metrics present |
|---|---|---|
| `/portfolio/risk/status` | PASS (1.3s) | date, equity, symbols, aggregate, regime, game_plan_readiness |

## Evidence
- `evidence/04-portfolio/` (curl transcripts captured during run)

## Deviations / Issues
- Portfolio endpoints are read-only views (build/evaluate = state/daily-allocation/risk-status); plan's "build + evaluate" maps to these. No issue.
