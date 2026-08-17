---
name: patchtst-implementation
status: phase-1-done
purpose: the real record of implementing PatchTST's walk-forward backtest against the shared infrastructure — the ablation/control counterpart to lpatchtst.
---

# 20 — patchtst — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/patchtst/compute.py` | Edited | `MIN_BARS` raised 90→100. Extracted `_fit_and_forecast()` — `compute()`'s external behavior unchanged. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/patchtst/backtest.py` | New | `patchtst_step` (direction hit + RMSE/MAE + weights save) + `run_patchtst_backtest`, same shape as lpatchtst's. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/patchtst/naive_baseline.py` | New | RMSE/MAE-only naive baseline. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/patchtst/spec.yaml` | Not touched | Already at the decided 6 `time_formats`; purpose text already cites the correct, unmiscited 54.1%/0.86 benchmark (this angle's design doc explicitly flags it as "no correction needed here, unlike LSTM/LPatchTST"). |
| `vinu-initial-analysis/tests/test_patchtst_backtest.py` | New | 5 tests. |

## A note on the benchmark citation check

lstm's implementation record (`14-lstm/01-implementation.md`) flagged a
standing reminder to cross-check patchtst's cited benchmark, after
finding lpatchtst and lstm both had miscited figures. Checked here: this
angle's design doc (`20-patchtst.md` SS3) already states plainly that its
54.1%/Sharpe-0.86 figure is "real, verified... no correction needed here"
— so this is 2-for-3, not 3-for-3: the design-doc-authoring pass already
did this check for patchtst before implementation reached it. Nothing to
fix here.

## How it was implemented

Group A, structurally identical to lpatchtst minus the LSTM branch —
literally the same shared `PatchEncoderBranch` (`_patch_transformer.py`)
run standalone. This angle's entire purpose (per its design doc) is
**not** to be a good standalone forecaster — it's the ablation control
that lets lpatchtst's own "does the LSTM branch help" question actually
be answered on this project's real data, not just trusted from the
source paper. Kept every config knob (lookback, patch size, d_model,
epochs, seed) identical to lpatchtst's so any measured difference is
attributable to the LSTM branch alone.

## Testing

5 new tests + 4 pre-existing (unchanged — its `n=40`/`n=200` fixtures
straddle both the old and new `MIN_BARS`). Same coverage shape as
lpatchtst/lstm's test suites.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars (same
dataset as every other Phase-1 `1D` check this session) → 25 rows in
4.83s. Tags matched standalone `tag_row`. Weights saved and reloadable —
a real trained transformer encoder's full state (`branch.embed.weight`,
`branch.encoder.layers.0.self_attn.in_proj_weight`, and friends).
Storage round-trip: zero column mismatches. `query_slice`'s grouped
hit-rate-by-day-of-week matched a hand aggregation.

**Real finding — the ablation comparison, on this project's own data**:

| | Directional accuracy | RMSE | MAE |
|---|---|---|---|
| patchtst (this angle) | 44% | 5.28 | 3.93 |
| lpatchtst (LSTM+patch hybrid) | 48% | 11.52 | — |
| naive baseline | — | 3.80–6.50 (varies by angle's own naive run) | 2.61 |

On this real, small (25-step), single-symbol sample, lpatchtst's hit rate
(48%) does edge out plain patchtst's (44%) — directionally consistent
with the source paper's own finding that "patch segmentation alone is
insufficient without robust temporal state encoding," though at this
sample size a 4-point gap isn't strong evidence on its own. Both angles
underperformed the naive baseline on RMSE here, same finding pattern as
every DLinear-family angle checked this session on this particular
symbol/date range. Recorded plainly — this is exactly the kind of
same-data, same-recipe comparison this angle exists to enable, and the
answer is a real, measured one now, not an assumed one.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../13-lpatchtst/01-implementation.md` — the hybrid this angle is the control for.
- `../../04-enhancement-of-each-angle/20-patchtst.md` — the decided design.
