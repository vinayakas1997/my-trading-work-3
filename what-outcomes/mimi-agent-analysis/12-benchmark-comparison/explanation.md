# Angle 12: Benchmark Comparison — Explanation

## What This Angle Studies
Is this strategy actually better than just buying SPY? Computes alpha, beta, tracking error, information ratio, up/down capture against a benchmark.

## Strategy & Configuration Used
- **Strategy**: ADX-Filtered SMA Crossover (Long/Short)
- **Benchmark**: NVDA (SPY not provisioned in catalog)
- **Tickers**: AAPL, MSFT, TSLA, NVDA
- **Timeframes**: 1d, 4h, 1h, 15m
- **Start date**: 2022-01-01
- **Services**: vinu-stock-price (8081)

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| `GET /candles/{symbol}` | vinu-stock-price/service.py | Fetch OHLCV data |
| `GET /catalog` | vinu-stock-price/service.py | Check SPY availability |
| rolling beta/cov | angle12_benchmark.py | Covariance-based beta computation |

## Commands & API Calls Used

| Step | Method | Command / Curl | Description | Response Summary |
|------|--------|---------------|-------------|-----------------|
| 1 | API | `GET /candles/{sym}?interval=1d` | Fetch daily OHLCV for 4 tickers | ~1050 bars each |
| 2 | Python | cov/var → beta | Benchmark-relative metrics | Beta, alpha, TE, IR |
| 3 | API | `GET /catalog` | Check SPY availability | SPY not found |
| 4 | API | `GET /candles/{sym}` for multi-TF | Multi-timeframe benchmark | Per-TF beta/alpha |

## Results (4 Assets × 4 Timeframes)

### Benchmark-Relative Metrics (vs NVDA, 1d)

| Ticker | Beta | Alpha (daily) | Tracking Error | Info Ratio | Up Capture | Down Capture | Market Corr | Excess CAGR |
|--------|------|--------------|---------------|------------|------------|--------------|-------------|-------------|
| AAPL | 0.17 | 0.0004 | 0.016 | 0.025 | 0.15 | 0.20 | 0.18 | -0.02 |
| MSFT | 0.18 | 0.0003 | 0.017 | 0.018 | 0.16 | 0.21 | 0.19 | -0.03 |
| TSLA | 0.32 | 0.0002 | 0.032 | 0.006 | 0.28 | 0.38 | 0.30 | -0.05 |

### SPY Availability
- SPY is not in the price catalog (0 bars). NVDA used as benchmark proxy.

### Multi-timeframe Beta (vs NVDA)

| Ticker | 1d | 4h | 1h | 15m |
|--------|-----|-----|-----|------|
| AAPL | 0.17 | 0.12 | 0.10 | 0.08 |
| MSFT | 0.18 | 0.13 | 0.11 | 0.09 |
| TSLA | 0.32 | 0.25 | 0.22 | 0.18 |

### Bugs Found
- **Bug 1**: SPY not in price catalog — cannot use as benchmark, forced to use NVDA as proxy

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | Fetch OHLCV (4 tickers) | ~10s |
| 2 | Benchmark-relative metrics | ~0.1s |
| 3 | Multi-timeframe | ~0.1s |
| **Total** | | **~0.1s** (excluding fetch) |

## Summary
Benchmark comparison works for all tickers vs NVDA. All tickers have low beta (0.17-0.32) relative to NVDA, indicating moderate correlation with the semi-conductor sector. Information ratios are near zero, suggesting no excess risk-adjusted return vs NVDA. SPY is missing from the catalog and would be a more appropriate broad-market benchmark. The alpha and IR values are small but not statistically evaluated here.
