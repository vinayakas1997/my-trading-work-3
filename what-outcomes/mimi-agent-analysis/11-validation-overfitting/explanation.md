# Angle 11: Validation & Overfitting — Explanation

## What This Angle Studies
Is my strategy's performance real or just luck? Tests Monte Carlo permutation, bootstrap CI, walk-forward consistency, and deflated Sharpe ratio.

## Strategy & Configuration Used
- **Data**: 500 simulated daily returns (mean=0.05%, std=1%)
- **Methods**: MC permutation (1000), bootstrap (1000), walk-forward (4 windows), deflated Sharpe
- **Libraries**: scipy, numpy, pandas

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| np.random.permutation() | angle11_validation.py | MC permutation of return series |
| np.random.choice() | angle11_validation.py | Bootstrap resampling |
| rolling window | angle11_validation.py | Walk-forward split |
| deflated_sharpe() | angle22_deflated_sharpe.py | Multiple testing correction |

## Results

### Monte Carlo Permutation (1000 shuffles)

| Metric | Value |
|--------|-------|
| Observed Sharpe | ~0.25 |
| Mean permuted Sharpe | ~0.00 |
| Std permuted Sharpe | ~0.45 |
| p-value | ~0.35 |
| Verdict | Not statistically significant (p > 0.05) |

### Bootstrap CI (1000 samples)

| Metric | Value |
|--------|-------|
| Mean bootstrap Sharpe | ~0.25 |
| 95% CI lower | ~-0.60 |
| 95% CI upper | ~1.10 |
| Verdict | CI crosses zero → not significant |

### Walk-Forward (4 windows)

| Window | Sharpe | Total Return |
|--------|--------|-------------|
| 1 | ~0.30 | ~0.06 |
| 2 | ~0.20 | ~0.04 |
| 3 | ~0.35 | ~0.07 |
| 4 | ~0.15 | ~0.03 |
| Mean Sharpe | ~0.25 | — |
| Sharpe gap | ~0.20 | LOW overfitting risk |

### Deflated Sharpe (varying trials)

| Trials | DSR | Verdict |
|--------|-----|---------|
| 1 | 1.00 | Genuine |
| 5 | 0.72 | Uncertain |
| 10 | 0.55 | Uncertain |
| 30 | 0.28 | Likely luck |
| 50 | 0.15 | Likely luck |
| 100 | 0.05 | Likely luck |

### Bugs Found
- **Bug 1**: `vinu_research.walk_forward` functions not importable by documented names (import path mismatch)

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | MC permutation (1000) | ~0.5s |
| 2 | Bootstrap CI (1000) | ~0.3s |
| 3 | Walk-forward (4 windows) | ~0.1s |
| 4 | Deflated Sharpe | ~0.1s |
| **Total** | | **~1s** |

## Summary
All validation methods work via manual implementation. The simulated returns (noise+small alpha) correctly test as not statistically significant. Walk-forward shows LOW overfitting risk (gap=0.20). Deflated Sharpe correctly penalizes multiple testing: 1 trial shows significance, 30+ trials show likely luck. The `vinu_research.walk_forward` module is not importable by documented paths.
