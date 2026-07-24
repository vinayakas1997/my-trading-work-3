# Task 1: Implement block_bootstrap_permutation

**Status:** DONE

## Purpose

Add a circular block bootstrap permutation test for trade P&Ls that preserves short-range dependence between consecutive trades. The existing `monte_carlo_permutation` does a full i.i.d. shuffle, which destroys any autocorrelation in trade outcomes — a less realistic null for strategies where winners/losers cluster.

## Approach

- Randomly select circular blocks of size `block_size` (default 5) with replacement from the trade P&L array
- Concatenate blocks to form a resampled sequence of the same length
- Compute Sharpe on each resampled sequence via equity-curve method
- P-value = fraction of resampled Sharpes >= actual Sharpe
- Accept optional `rng: np.random.Generator` for reproducibility
- Return same dict shape as existing functions for uniform consumption by `compute_validation_verdict`

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-simulator/vinu_simulator/engine/validation.py` | 9-74 | Added `block_bootstrap_permutation()` function |

## Verification

- [x] Returns correct structure with sufficient data
- [x] Returns `minimum_met: False, p_value: 1.0` for < 3 trades
- [x] Handles single trade, empty list
- [x] Block size 1 degenerates to bootstrap (works correctly)
- [x] Reproducible with same RNG seed
