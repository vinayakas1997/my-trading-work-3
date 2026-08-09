---
name: lpatchtst-implementation
status: phase-1-done
purpose: the real record of implementing LPatchTST's walk-forward backtest against the shared infrastructure.
---

# 13 — lpatchtst — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/lpatchtst/compute.py` | Edited | `MIN_BARS` raised 90→100. Extracted `_fit_and_forecast()` (returns the trained model too) — `compute()`'s external behavior unchanged. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/lpatchtst/backtest.py` | New | `lpatchtst_step` (direction hit + RMSE/MAE fields + weights save) + `run_lpatchtst_backtest`, same shape as DLinear's, extended with RMSE/MAE per the decided design. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/lpatchtst/naive_baseline.py` | New | RMSE/MAE-only naive baseline, same convention as every other DLinear-family angle. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/lpatchtst/spec.yaml` | Edited | `purpose` text still repeated the stale, miscited "~54% directional accuracy" claim the design doc corrected to 57.7% (arXiv:2603.01820) — fixed with a pointer to the correction. (`time_formats` already at the decided 6.) |
| `vinu-initial-analysis/tests/test_lpatchtst_backtest.py` | New | 5 tests. |

## How it was implemented

Group A, structurally like DLinear: a fresh model (LSTM branch +
`PatchEncoderBranch`, the exact same shared patch-attention module
`patchtst` uses standalone) trained from scratch at every walk-forward
step, every step's weights saved via `WeightsStore`. Direction-match hit
(no confidence interval), **plus** `close_sq_error`/`close_abs_error`
fields on the real angle's own step — this angle's decided design adds
RMSE/MAE alongside the hit rate (unlike DLinear/iTransformer, which only
have the naive baseline's RMSE for comparison, not their own).

## Testing

5 new tests + 4 pre-existing (all still pass unchanged, confirming the
refactor didn't change `compute()`'s behavior). Covers: row count, tag
correctness, hit/RMSE/MAE field consistency, weights saved/reloadable,
naive baseline's absent `hit`/`weights_ref` columns.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars → 25
rows in 6.81s. Tags matched standalone `tag_row`. Weights saved and
reloadable (`lstm.weight_ih_l0` and friends — a real LSTM's state).
Storage round-trip and `query_slice` verified exactly against a hand
pandas `groupby`.

**Real finding**: 48% directional accuracy on this real (small, 25-step)
sample — below the corrected paper benchmark of 57.7% (arXiv:2603.01820).
Naive again beat this angle on RMSE (6.50 vs. 11.52). Recorded honestly,
same as every prior angle's real finding this session — one small,
single-symbol sample isn't strong evidence the architecture doesn't earn
its 57.7% figure on a genuinely different asset universe/date range (the
paper's own benchmark is futures data 2010-2025, not this project's
equity/date range, a caveat the design doc itself already flags), but the
number as actually measured here is what it is.

**Full `vinu-initial-analysis` suite**: 283 passed (up from 278
pre-this-angle — the 5 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures, no new failures.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/13-lpatchtst.md` — the decided design, including the source-citation correction.
