# Task 5: Dynamic Ledoit-Wolf Covariance

**Status:** PENDING

## Purpose

Implement shrinkage-estimated covariance matrix (Ledoit-Wolf) across an arbitrary symbol set, with dynamic estimation that can pick up regime shifts.

## Approach

- Shrinkage estimator: convex combination of sample covariance and a structured target (constant-correlation model)
- Dynamic estimation: rolling window with optional exponential weighting
- Handles singular/ill-conditioned matrices via shrinkage

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_tools/compute/risk/covariance.py` | — | Created |

## Verification

- [x] Shrinkage estimator produces well-conditioned matrix for small symbol sets
- [x] Dynamic estimation picks up correlation regime shift in synthetic basket test
