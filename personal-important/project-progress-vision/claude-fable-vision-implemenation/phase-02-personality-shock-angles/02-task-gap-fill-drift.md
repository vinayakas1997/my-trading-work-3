# Task 2: Gap Fill Rate, Vol Persistence, Drift Persistence

**Status:** PENDING

## Purpose

Compute post-shock behavioral stats: gap_fill_rate, vol_persistence (from Phase 1 GARCH), drift_persistence_days.

## Approach

- gap_fill_rate: for each shock gap, measure how much fills within N sessions; aggregate with confidence interval
- vol_persistence: read Phase 1 GARCH persistence parameter (alpha+beta) for symbol
- drift_persistence_days: autocorrelation decay of post-shock directional drift
- All fields carry sample size + CI

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_initial_analysis/angles/shock_personality/compute.py` | — | Extended |

## Verification

- [x] vol_persistence matches Phase 1 GARCH parameter exactly (no separate estimation)
- [x] Low-sample symbols get wide CIs, never confident-looking point estimates
