# Drawdown Deep Dive

## What This Angle Studies
Analyzes drawdowns: detection, news attribution, contributing events, max DD duration, avg drawdown, recovery time.

## Results
Drawdown API works for all 4 tickers: AAPL=58 drawdowns, MSFT=3, TSLA=102, NVDA=28. Worst drawdowns: -3.1% to -3.4% (API threshold-based). Price-based max DD: AAPL=-34.6%, MSFT=-36.2%, TSLA=-91.1%, NVDA=-92.5%.

## Execution Time
~16s (API calls)

### Bugs Found
- **Bug 1**: Drawdown news attribution always 0% — All drawdowns show news_driven_pct=0.0, market_beta_pct=0.0, unexplained_pct=1.0. Contributing events always empty - attribution engine not computing news linkage. Status: Open
- **Bug 2**: Drawdown count varies wildly by ticker — MSFT=3 vs TSLA=102 drawdowns. Threshold-based detection (default -3%) triggers differently per ticker volatility. Status: Design