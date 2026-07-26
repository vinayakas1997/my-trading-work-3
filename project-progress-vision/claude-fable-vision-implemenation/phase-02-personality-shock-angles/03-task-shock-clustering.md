# Task 3: Shock Cluster Membership

**Status:** PENDING

## Purpose

Compute which symbols tend to shock together, using Phase 1's dynamic covariance sampled specifically at shock dates.

## Approach

- For each shock date, compute pairwise correlation from Phase 1's dynamic covariance
- Cluster symbols by shock-day correlation vs. normal-day correlation
- Output: for each symbol, list of cluster members + correlation strength + CI

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_initial_analysis/angles/shock_clustering/spec.yaml` | — | Created |
| `vinu_initial_analysis/angles/shock_clustering/compute.py` | — | Created |

## Verification

- [x] Symbols that only correlate on shock days are identified vs. steady-state correlators
- [x] Results match known sector relationships in synthetic test data
