---
name: backtest-diagnose
description: Error taxonomy + hard-gate checklist for failed backtests
category: tool
---

## Backtest Diagnosis — Error Taxonomy

### Error Type 1: Zero Trades
**Symptoms**: Trade count = 0, flat equity curve.

**Causes**:
- Signal condition never triggered (wrong indicator period)
- Price filter too restrictive (volume/price thresholds)
- Date range too short for signal crossover
- Interval mismatch (1m signal on 1D data)

**Fixes**:
- Verify signal logic with a single-candle test
- Reduce threshold filters temporarily to confirm signal fires
- Extend date range to 5+ years

### Error Type 2: Poor Sharpe (< 0.5)
**Symptoms**: Positive returns but high volatility.

**Causes**:
- No volatility filter on entries
- Signal catches trends but holds through reversals
- Stop-loss too wide or missing

**Fixes**:
- Add ATR-based stop loss (2-3x ATR)
- Add ADX > 25 filter to avoid ranging markets
- Reduce holding period

### Error Type 3: High Drawdown (> 40%)
**Symptoms**: Equity curve has large peaks and deep valleys.

**Causes**:
- No position sizing
- All-in on every signal (no capital allocation)
- No regime detection

**Fixes**:
- Apply fixed-fraction sizing (1-2% risk per trade)
- Add market regime filter (trending vs ranging)
- Implement max-consecutive-losses circuit breaker

### Error Type 4: Overfitting
**Symptoms**: Excellent IS performance, poor OOS.

**Causes**:
- Too many parameters optimized
- Multiple indicator combinations tested
- Data snooping

**Fixes**:
- Walk-forward validation (minimum 3 windows)
- Keep parameter count < 5
- OOS period must be ≥ 20% of total data

### Hard-Gate Checklist
Before deploying any strategy:
- [ ] IS Sharpe > 1.0 and OOS Sharpe > 0.7
- [ ] OOS MaxDD < 1.5x IS MaxDD
- [ ] Trade count ≥ 30
- [ ] Profit factor > 1.5
- [ ] Passes walk-forward (min 3 windows)
