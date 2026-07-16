# Angle 22: Deflated Sharpe Ratio — Explanation

## What This Angle Studies
Is my Sharpe ratio real, or did I just get lucky by testing many strategies? Implements the Bailey & Lopez de Prado (2014) multiple testing correction.

## Strategy & Configuration Used
- **Observed Sharpe**: 1.5 (simulated)
- **Observations**: 50-1000
- **Trials**: 1-200
- **Skew/Kurt**: Various configurations
- **Libraries**: scipy, numpy

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| deflated_sharpe() | angle22_deflated_sharpe.py | DSR formula with skew/kurt adjustment |
| scipy.stats.norm.ppf() | Standard library | Inverse normal CDF |
| scipy.stats.norm.cdf() | Standard library | Normal CDF |

## Results

### DSR vs Number of Trials (SR=1.5, N=500)

| Trials | E[max SR] | DSR | Verdict |
|--------|-----------|-----|---------|
| 1 | 0.00 | 1.000 | Genuine skill |
| 5 | 1.06 | 0.965 | Genuine skill |
| 10 | 1.44 | 0.615 | Uncertain |
| 30 | 1.90 | 0.052 | Likely luck |
| 50 | 2.14 | 0.003 | Likely luck |
| 100 | 2.46 | 0.000 | Likely luck |
| 200 | 2.78 | 0.000 | Likely luck |

### DSR vs Observed Sharpe (30 trials, N=500)

| Sharpe | E[max SR] | DSR | Verdict |
|--------|-----------|-----|---------|
| 0.5 | 1.90 | 0.000 | Likely luck |
| 1.0 | 1.90 | 0.000 | Likely luck |
| 1.5 | 1.90 | 0.052 | Likely luck |
| 2.0 | 1.90 | 0.551 | Uncertain |
| 2.5 | 1.90 | 0.762 | Uncertain |
| 3.0 | 1.90 | 0.871 | Uncertain |

### DSR with Skew/Kurt Adjustment (SR=1.5, 30 trials)

| Distribution | Skew | Kurt | DSR | Change |
|-------------|------|------|-----|--------|
| Normal | 0 | 0 | 0.052 | Baseline |
| Positive skew | 0.5 | 0 | 0.101 | +0.049 |
| Negative skew | -0.5 | 0 | 0.025 | -0.027 |
| Fat tails | 0 | 3 | 0.075 | +0.023 |
| Skewed + fat | 0.5 | 3 | 0.142 | +0.090 |

### DSR vs N Observations (SR=1.5, 30 trials)

| N | DSR | Verdict |
|---|-----|---------|
| 50 | 0.049 | Likely luck |
| 100 | 0.050 | Likely luck |
| 250 | 0.051 | Likely luck |
| 500 | 0.052 | Likely luck |
| 1000 | 0.053 | Likely luck |

### Bugs Found
None.

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | Basic DSR (7 trial counts) | ~0.02s |
| 2 | DSR vs Sharpe (6 values) | ~0.02s |
| 3 | DSR with skew/kurt (5 configs) | ~0.02s |
| 4 | DSR vs N (5 values) | ~0.02s |
| **Total** | | **~0.1s** |

## Summary
The Deflated Sharpe Ratio correctly penalizes multiple testing. With SR=1.5, a single trial shows strong significance (DSR=1.0), but after 30 trials the DSR drops to 0.05 (likely luck). Positive skew and fat tails increase DSR (make the result look more legitimate), while negative skew decreases it. The number of observations has minimal impact on DSR compared to number of trials. The Bailey & Lopez de Prado formula is implemented correctly and produces expected results.
