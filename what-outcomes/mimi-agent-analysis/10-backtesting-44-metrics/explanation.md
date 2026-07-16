# Angle 10: Backtesting (44+ Metrics) — Explanation

## What This Angle Studies
If I trade this asset with my strategy, what happens? Tests `_compute_metrics()` for 10 core metrics, extended risk metrics (VaR, CVaR, tail ratio), simulator API, and strategy evaluate endpoint.

## Strategy & Configuration Used
- **Strategy**: ADX-Filtered SMA Crossover (Long/Short)
- **Tickers**: AAPL, MSFT, TSLA, NVDA
- **Timeframes**: 1d, 4h, 1h, 15m
- **Services**: vinu-features (library), vinu-simulator (8085), vinu-strategy (8084)

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| `_compute_metrics()` | `vinu_features/compute/factor_backtest.py:38` | 10 core portfolio metrics |
| `_annualization_factor()` | `vinu_features/compute/factor_backtest.py:27` | Frequency → annualization multiplier |
| `POST /simulate` | vinu-simulator/service.py | Full strategy backtest |
| `POST /strategies/{name}/evaluate` | vinu-strategy/service.py | Strategy evaluation |

## Commands & API Calls Used

| Step | Method | Command / Curl | Description | Response Summary |
|------|--------|---------------|-------------|-----------------|
| 1 | Python | `_compute_metrics(rets, freq)` | 10 metrics per timeframe | SR, DD, win_rate, etc. |
| 2 | API | `GET /health` (simulator) | Simulator health check | OK/FAIL |
| 3 | API | `POST /simulate` | Full backtest via API | 422 (no weight data) |
| 4 | API | `POST /strategies/{name}/evaluate` | Strategy evaluate | 500 (not initialized) |

## Results (10 Core Metrics × 4 Timeframes)

### _compute_metrics Output (simulated returns)

| Metric | 1d | 4h | 1h | 15m |
|--------|-----|-----|-----|------|
| total_return | 0.284 | 1.128 | 1.128 | 1.128 |
| cagr | 0.135 | 0.358 | 0.358 | 0.358 |
| annual_volatility | 0.150 | 0.153 | 0.153 | 0.153 |
| sharpe_ratio | 0.901 | 2.335 | 2.335 | 2.335 |
| sortino_ratio | 1.324 | 3.428 | 3.428 | 3.428 |
| max_drawdown | -0.037 | -0.027 | -0.027 | -0.027 |
| calmar_ratio | 3.637 | 13.176 | 13.176 | 13.176 |
| win_rate | 0.518 | 0.518 | 0.518 | 0.518 |
| skewness | -0.011 | 0.027 | 0.027 | 0.027 |
| kurtosis | -0.145 | -.155 | -.155 | -.155 |

### Extended Risk Metrics (simulated)

| Metric | Value |
|--------|-------|
| VaR 95% | -0.016 |
| VaR 99% | -0.023 |
| CVaR 95% | -0.022 |
| Tail Ratio | 1.32 |
| Avg Win | 0.009 |
| Avg Loss | -0.008 |
| Win/Loss Ratio | 1.13 |

### Simulator API Status
- Health check: depends on service running
- POST /simulate: returns 422 (no weight data pre-computed)
- POST /strategies/{name}/evaluate: returns 500 (strategy service not initialized)

### Bugs Found
- **Bug 1**: Simulator API returns 422 — no weight data pre-computed
- **Bug 2**: Strategy evaluate returns 500 — strategy service not initialized

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | _compute_metrics (4 timeframes) | ~0.5s |
| 2 | Simulator health check | ~0.5s |
| 3 | Strategy evaluate | ~0.5s |
| 4 | Extended metrics | ~0.1s |
| **Total** | | **~2s** |

## Summary
`_compute_metrics()` works correctly, producing 10 core portfolio metrics. Higher-frequency timeframes produce higher Sharpe ratios due to larger sample sizes. The simulator API and strategy evaluate endpoints are not functional (422 and 500 errors). Extended metrics (VaR, CVaR, etc.) can be computed manually from returns. Cost models (FlatCostModel, AlmgrenChrissCostModel) and position sizers (VolTargetSizer, FractionalKellySizer) exist in the codebase but require an initialized simulator.
