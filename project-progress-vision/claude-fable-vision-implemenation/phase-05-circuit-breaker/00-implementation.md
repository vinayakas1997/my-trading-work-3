# Phase 5: Circuit Breaker / Kill Switch

**Status:** IN PROGRESS
**Started:** 2026-07-26
**Source doc:** ../claude-fable-vision/phase-05-circuit-breaker.md
**Depends on:** Phase 1, Phase 3
**Blocks:** Phase 6

## What It Delivers

A hard, deterministic enforcement layer inside `vinu-live`:
- Max daily loss threshold
- Max aggregate VaR (computed from Phase 1's dynamic covariance across Phase 3's live book)
- Max greeks exposure
- Max position count
- Clustering-aware aggregate check (not naive per-symbol sum)
- Trading halts on breach — no order reaches broker without clearing this gate

Kept separate from Phase 1's risk-math library. Thresholds are deployment-time settings.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu_live/breaker/__init__.py` | vinu-live | create |
| `vinu_live/breaker/limits.py` | vinu-live | create |
| `vinu_live/breaker/engine.py` | vinu-live | create |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-breaker-limits.md` | Hard limit definitions and threshold config | PENDING |
| 2 | `02-task-breaker-engine.md` | Circuit breaker engine — cluster-aware aggregate VaR check, pre-order gate | PENDING |

## Dependencies Met

- [x] Phase 1 completed (risk-math formulas, dynamic covariance)
- [x] Phase 3 completed (live book ledger)
