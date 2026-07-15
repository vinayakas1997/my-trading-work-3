# Benchmark Comparison — Bugs

| # | Bug | Error | Root Cause | Status |
|---|-----|-------|------------|--------|
| 1 | SPY (S&P 500 ETF) not in data catalog | GET /candles/SPY returns count=0 | Only TICKERS (AAPL, MSFT, TSLA, NVDA) were backfilled via Alpaca IEX. SPY/benchmarks not provisioned. | Open |
