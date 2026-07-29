# Phase 2: Personality / Shock-Clustering Angles

**Status:** IN PROGRESS
**Started:** 2026-07-26
**Source doc:** ../claude-fable-vision/phase-02-personality-shock-angles.md
**Depends on:** Phase 1
**Blocks:** Phase 4, Phase 7

## What It Delivers

New angle folders inside `vinu-initial-analysis` following the existing self-contained-angle pattern:
- Shock-tagging step: joins price gaps + volatility z-score spikes with news events
- `gap_fill_rate` — how often/ much a gap closes within N sessions
- `vol_persistence` — from Phase 1's GARCH persistence parameter
- `drift_persistence_days` — how long post-shock drift lasts
- `shock_cluster_membership` — which symbols shock together (from Phase 1's dynamic covariance sampled at shock dates)

Every field carries sample size + confidence interval.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu_initial_analysis/angles/shock_personality/spec.yaml` | vinu-initial-analysis | create |
| `vinu_initial_analysis/angles/shock_personality/compute.py` | vinu-initial-analysis | create |
| `vinu_initial_analysis/angles/shock_clustering/spec.yaml` | vinu-initial-analysis | create |
| `vinu_initial_analysis/angles/shock_clustering/compute.py` | vinu-initial-analysis | create |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-shock-tagging.md` | Shock-tagging: price gaps + vol z-score spikes + news cross-reference | PENDING |
| 2 | `02-task-gap-fill-drift.md` | gap_fill_rate, vol_persistence, drift_persistence_days | PENDING |
| 3 | `03-task-shock-clustering.md` | shock_cluster_membership from dynamic covariance at shock dates | PENDING |

## Dependencies Met

- [x] Phase 1 completed (GARCH fit, dynamic covariance available)
