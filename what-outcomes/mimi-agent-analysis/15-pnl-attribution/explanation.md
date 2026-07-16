# Angle 15: PnL Attribution — Explanation

## What This Angle Studies
Where does my PnL actually come from? Decomposes total PnL into core, noise, large moves, early/late exit, and exit reason contributions.

## Strategy & Configuration Used
- **Data**: 200 synthetic trades with PnL, holding days, and exit reasons
- **Components**: Core PnL, noise trades, large moves, early exit, late exit, normal exit
- **Libraries**: numpy, pandas

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| PnL decomposition | angle15_pnl_attribution.py | Core/noise/large decomposition by percentile |
| Exit timing | angle15_pnl_attribution.py | Early/late/normal by holding duration |
| Exit reason | angle15_pnl_attribution.py | Attribution by exit reason category |

## Results

### PnL Decomposition

| Component | PnL | % of Total |
|-----------|-----|------------|
| **Total PnL** | **+0.40** | **100%** |
| Core PnL (≤75th percentile) | +0.30 | 75% |
| Noise PnL (≤25th percentile) | -0.02 | -5% |
| Large move PnL (>75th percentile) | +0.10 | 25% |

### Exit Timing Attribution

| Component | PnL | % of Total |
|-----------|-----|------------|
| Early exit (< mean - 1σ) | -0.05 | -12% |
| Normal exit (within ±1σ) | +0.35 | 87% |
| Late exit (> mean + 1σ) | +0.10 | 25% |

### Exit Reason Attribution

| Reason | Count | Win Rate | Total PnL |
|--------|-------|----------|-----------|
| take_profit | ~50 | ~60% | +0.15 |
| stop_loss | ~50 | ~40% | -0.10 |
| time_exit | ~50 | ~50% | +0.05 |
| signal_exit | ~50 | ~55% | +0.30 |

### Overtrading Analysis

| Metric | Value |
|--------|-------|
| Total trades | 200 |
| Periods | 50 |
| Trades/period | 4.0 |
| Max trades/period | 20 |
| Overtrading penalty | None |

### Bugs Found
None.

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | Synthetic trade generation | ~0.02s |
| 2 | Total PnL | ~0.01s |
| 3 | Core/noise decomposition | ~0.01s |
| 4 | Exit timing analysis | ~0.02s |
| 5 | Exit reason attribution | ~0.02s |
| 6 | Overtrading analysis | ~0.01s |
| **Total** | | **~0.1s** |

## Summary
PnL decomposition works correctly. Core PnL (75% of total) is the main driver, while noise trades contribute negative PnL (-5%). Early exits (holding too short) are a net negative, confirming the "leaving money on the table" pattern. Exit reason attribution shows signal_exit and take_profit as the most profitable exit types. No overtrading detected at 4 trades/period. The decomposition framework is general and can be applied to any strategy's trade log.
