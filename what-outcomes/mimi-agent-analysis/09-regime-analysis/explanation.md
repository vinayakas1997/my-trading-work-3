# Regime Analysis

## What This Angle Studies
Classifies market into 4 regimes (bull, bear, high_vol, sideways) and computes per-regime metrics (count, return, Sharpe, win_rate).

## Results
All 4 regimes populated across all tickers. High_vol has ~309 bars (30% of data, consistent with 70th percentile threshold). Bull/bear regimes show extreme per-regime Sharpe due to regime classification methodology (look-ahead in definition). Representative: AAPL bull SR=37.2 (n=142), bear SR=-36.3 (n=125), high_vol SR=1.0 (n=309), sideways SR=-0.1 (n=453).

## Execution Time
~0.03s

### Bugs Found
- **Bug 1**: Regime Sharpe values are unrealistically extreme — Bull regime Sharpe ~37, Bear regime ~-36. Regime definition uses contemporaneous returns: a +1% day IS a bull day by definition, so within-regime Sharpe amplifies the classification itself. Status: Design limitation