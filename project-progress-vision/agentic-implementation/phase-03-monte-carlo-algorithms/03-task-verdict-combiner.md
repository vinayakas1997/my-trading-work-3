# Task 3: Implement compute_validation_verdict

**Status:** DONE

## Purpose

Provide a single, documented pass/fail verdict that combines all validation sub-results. This is what Phase 04 gates on — the threshold logic is centralized here rather than scattered across `vinu-research`.

## Approach

Evaluates five sub-results with documented thresholds:

| Sub-result | Key | Threshold | Rationale |
|---|---|---|---|
| monte_carlo | p_value | < 0.05 | Standard significance level |
| block_bootstrap | p_value | < 0.05 | Same null rejection bar |
| price_path | p_value | < 0.10 | Slightly looser — tougher null |
| walk_forward | consistency_rate | >= 0.60 | Majority of windows profitable |
| bootstrap | ci_low | > 0.0 | Sharpe 95% CI above zero |

Functions with `minimum_met: False` are skipped (not failed). Each produces a human-readable reason string.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-simulator/vinu_simulator/engine/validation.py` | 136-205 | Added `compute_validation_verdict()` function |

## Verification

- [x] Passes when all sub-checks pass
- [x] Fails when any single sub-check fails
- [x] Skips (does not fail) sub-results with insufficient data
- [x] Skips missing sub-results gracefully
- [x] Boundary threshold tests for each rule
