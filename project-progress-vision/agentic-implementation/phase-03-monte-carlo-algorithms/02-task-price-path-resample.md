# Task 2: Implement price_path_resample

**Status:** DONE

## Purpose

Add a block-bootstrap resampling test on the daily return series itself. Unlike trade-P&L shuffling (which tests trade-execution order), this tests whether the observed Sharpe ratio is distinguishable from what arises from the autocorrelation and volatility structure of price changes alone.

## Approach

- Same circular block-bootstrap technique as `block_bootstrap_permutation` but applied to daily returns
- Default block size = 20 (roughly one trading month)
- Minimum data requirement = `block_size * 2`
- P-value = fraction of resampled paths with Sharpe >= actual Sharpe
- Accept optional `rng: np.random.Generator` for reproducibility

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-simulator/vinu_simulator/engine/validation.py` | 76-134 | Added `price_path_resample()` function |

## Verification

- [x] Returns correct structure with sufficient data
- [x] Returns `minimum_met: False` when observations < block_size * 2
- [x] Near-zero Sharpe produces high p-value (test confirms)
- [x] Reproducible with same RNG seed
