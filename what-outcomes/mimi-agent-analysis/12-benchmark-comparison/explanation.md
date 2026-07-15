# Benchmark Comparison

## What This Angle Studies
Computes benchmark-relative metrics: beta, alpha, tracking_error, information_ratio, up_capture, down_capture, market_correlation.

## Results
SPY not available in data catalog (0 bars). Used NVDA as proxy benchmark. Beta: AAPL=0.17, MSFT=0.18, TSLA=0.32, NVDA=1.0. Information ratios low (<0.02) due to weak alpha signals in 2022-2024 period.

## Execution Time
~0.1s

### Bugs Found
- **Bug 1**: SPY (S&P 500 ETF) not in data catalog — GET /candles/SPY returns count=0. Only TICKERS (AAPL, MSFT, TSLA, NVDA) were backfilled via Alpaca IEX. SPY/benchmarks not provisioned.. Status: Open