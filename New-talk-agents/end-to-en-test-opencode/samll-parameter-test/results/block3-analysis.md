# Block 3 — Analysis

Cross-service smoke: initial-analysis angles, quant-core strategy evaluate + simulator backtest.

## 3a — initial-analysis
- Endpoint: `POST /analysis/runs` (or equivalent)
- Expected: angles JSON for AAPL / TSLA

| Ticker | Interval | Status | Angles present |
|---|---|---|---|
| AAPL | 1D | | |
| AAPL | 4H | | |
| AAPL | 1H | | |
| TSLA | 1D | | |
| TSLA | 4H | | |
| TSLA | 1H | | |

## 3b — quant-core strategy evaluate
- Strategy: `e2e_easy_sma_crossover`
- Expected: evaluation output with positions/signals

| Ticker | Interval | Status | Signals produced |
|---|---|---|---|
| AAPL | 1D | | |
| TSLA | 1D | | |

## 3c — simulator backtest
- Strategy: `e2e_easy_sma_crossover`
- Expected: backtest metrics (returns, sharpe, etc.)

| Ticker | Interval | Status | Metrics present | run_id present |
|---|---|---|---|---|
| AAPL | 1D | | | |

## Evidence
- `evidence/block3-analysis/`

## Deviations / Issues
- (link to deviations/issues if any)
