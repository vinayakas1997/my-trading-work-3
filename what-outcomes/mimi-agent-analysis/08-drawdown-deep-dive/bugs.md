# Drawdown Deep Dive — Bugs

| # | Bug | Error | Root Cause | Status |
|---|-----|-------|------------|--------|
| 1 | Drawdown news attribution always 0% | All drawdowns show news_driven_pct=0.0, market_beta_pct=0.0, unexplained_pct=1.0 | Contributing events always empty - attribution engine not computing news linkage | Open |
| 2 | Drawdown count varies wildly by ticker | MSFT=3 vs TSLA=102 drawdowns | Threshold-based detection (default -3%) triggers differently per ticker volatility | Design |
