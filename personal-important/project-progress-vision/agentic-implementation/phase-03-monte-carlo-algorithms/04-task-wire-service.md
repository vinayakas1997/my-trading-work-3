# Task 4: Wire New Functions into Service Layer

**Status:** DONE

## Purpose

Connect the new validation algorithms into `_run_validation_and_attribution()` so they're actually computed when a simulation request has `run_validation=True`.

## Approach

- Import `block_bootstrap_permutation`, `price_path_resample`, and `compute_validation_verdict` alongside the existing validation imports
- Call `block_bootstrap_permutation()` with the same trade P&Ls used by `monte_carlo_permutation`
- Call `price_path_resample()` with `daily_returns` and actual Sharpe
- Add results to the validation dict under `block_bootstrap` and `price_path` keys
- After all sub-results are assembled, add `validation["verdict"] = compute_validation_verdict(validation)`

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-simulator/vinu_simulator/service.py` | 473-477, 490-517 | Added imports, calls, and verdict computation |

## Verification

- [x] `block_bootstrap` and `price_path` keys present in validation dict
- [x] `verdict` key present with `passed: bool` and `reasons: list[str]`
- [x] All existing tests still pass
