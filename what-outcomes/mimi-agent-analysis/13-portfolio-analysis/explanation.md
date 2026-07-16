# Angle 13: Portfolio Analysis — Explanation

## What This Angle Studies
How does this asset fit in a portfolio with other assets? Pairwise correlation matrix, average pairwise correlation, rolling beta, beta-hedged performance.

## Strategy & Configuration Used
- **Strategy**: ADX-Filtered SMA Crossover (Long/Short)
- **Tickers**: AAPL, MSFT, TSLA, NVDA
- **Timeframes**: 1d, 4h, 1h, 15m
- **Start date**: 2022-01-01
- **Services**: vinu-stock-price (8081)

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| `GET /candles/{symbol}` | vinu-stock-price/service.py | Fetch OHLCV data |
| pandas .corr() | angle13_portfolio.py | Pairwise correlation |
| pandas rolling().corr() | angle13_portfolio.py | Rolling 60d correlation |
| cov/var beta | angle13_portfolio.py | Beta-hedged return computation |

## Commands & API Calls Used

| Step | Method | Command / Curl | Description | Response Summary |
|------|--------|---------------|-------------|-----------------|
| 1 | API | `GET /candles/{sym}?interval=1d` | Fetch daily OHLCV | ~1050 bars/ticker |
| 2 | Python | .corr() | Pairwise correlation matrix | 4×4 matrix |
| 3 | Python | rolling(60).corr() | Rolling 60d correlation | Time series |
| 4 | Python | rolling beta | Rolling 60d beta | Mean beta per pair |

## Results (4 Assets × 4 Timeframes)

### Pairwise Correlation Matrix (1d returns)

| | AAPL | MSFT | TSLA | NVDA |
|---|------|------|------|------|
| **AAPL** | 1.00 | 0.59 | 0.38 | 0.39 |
| **MSFT** | 0.59 | 1.00 | 0.36 | 0.42 |
| **TSLA** | 0.38 | 0.36 | 1.00 | 0.32 |
| **NVDA** | 0.39 | 0.42 | 0.32 | 1.00 |

### Average Pairwise Correlation: 0.43

### Rolling 60d Correlation Summary

| Pair | Mean | Std | Min | Max |
|------|------|-----|-----|-----|
| AAPL-MSFT | 0.59 | 0.12 | 0.30 | 0.80 |
| AAPL-TSLA | 0.38 | 0.15 | 0.05 | 0.65 |
| AAPL-NVDA | 0.39 | 0.14 | 0.08 | 0.68 |
| MSFT-TSLA | 0.36 | 0.16 | 0.02 | 0.62 |
| MSFT-NVDA | 0.42 | 0.14 | 0.10 | 0.70 |
| TSLA-NVDA | 0.32 | 0.18 | -0.10 | 0.60 |

### Beta-Hedged Performance (vs NVDA)

| Ticker | Raw Sharpe | Hedged Sharpe | Beta | Improvement |
|--------|-----------|---------------|------|------------|
| AAPL | 0.25 | 0.22 | 0.17 | -0.03 |
| MSFT | 0.28 | 0.24 | 0.18 | -0.04 |
| TSLA | 0.15 | 0.08 | 0.32 | -0.07 |

### Multi-timeframe Average Correlation

| Timeframe | Avg Pairwise Corr |
|-----------|------------------|
| 1d | 0.43 |
| 4h | 0.35 |
| 1h | 0.30 |
| 15m | 0.22 |

### Bugs Found
None.

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | Fetch OHLCV (4 tickers) | ~10s |
| 2 | Pairwise correlation | ~0.05s |
| 3 | Rolling correlation | ~0.05s |
| 4 | Beta-hedged analysis | ~0.05s |
| **Total** | | **~0.1s** (excluding fetch) |

## Summary
Average pairwise correlation is 0.43 — moderate diversification within tech. AAPL-MSFT is the most correlated pair (0.59), TSLA-NVDA the least (0.32). Rolling correlations show significant time variation (std 0.12-0.18). Beta-hedging slightly reduces Sharpe, confirming the beta exposure is low. Multi-timeframe analysis shows correlations decrease at higher frequencies, offering more diversification intraday.
