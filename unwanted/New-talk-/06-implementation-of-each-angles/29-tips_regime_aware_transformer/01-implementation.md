---
name: tips_regime_aware_transformer-implementation
status: phase-1-done
purpose: the real record of implementing the TIPS-inspired regime-gated forecaster's walk-forward backtest, and the real answer to whether its regime-gating earns its keep.
---

# 29 — tips_regime_aware_transformer — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/tips_regime_aware_transformer/compute.py` | Edited | Extracted `_fit_and_forecast()` (returns the trained model too) — `compute()`'s external behavior unchanged. `MIN_BARS` **not** touched (already 120, a real derived floor above the N=100 convention, per the design doc's explicit instruction not to adjust it). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/tips_regime_aware_transformer/backtest.py` | New | `tips_step` (direction hit + RMSE/MAE + weights save, same shape as DLinear/lpatchtst/patchtst/tft) + `run_tips_backtest`. No separate regime-split computation needed — `regime` is already a real per-row field from `compute()`'s own output, so the split is a query-time `groupby`, not new logic. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/tips_regime_aware_transformer/naive_baseline.py` | New | RMSE/MAE-only naive baseline. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/tips_regime_aware_transformer/spec.yaml` | Not touched | Already at the decided 6 `time_formats`. |
| `vinu-initial-analysis/tests/test_tips_regime_aware_transformer_backtest.py` | New | 5 tests. |

## A note on the paper-vs-code gap this angle's design doc already resolved

This angle's own design doc did real, substantial work before
implementation ever reached it: it verified the cited paper
(arXiv:2603.16985) is real, then found the actual code implements a
materially different, simpler architecture (regime-gated dual linear
heads via autocorrelation, not the paper's multi-teacher distillation
across causality/locality/periodicity biases) and explicitly decided
**not** to carry over the paper's benchmark numbers, since they'd
misattribute a different model's results. Nothing left to correct here —
this angle is built and evaluated as "TIPS-inspired," never compared
against a benchmark that doesn't apply to it.

## How it was implemented

Group A, structurally like DLinear/lpatchtst/patchtst/tft — a fresh
model (shared transformer encoder → regime-gated dual linear heads)
trained from scratch at every walk-forward step. The one thing genuinely
specific to this angle is already handled by storage/query, not new
backtest logic: `compute()`'s real output already stores `regime`
("momentum" or "mean_reversion") per row, so `query_slice`/`groupby`
directly answers the design's core validation question — "does each
head actually perform better within its own claimed regime" — without
needing a dedicated aggregation function.

## Testing

5 new tests + 4 pre-existing (unchanged — `n=60`/`n=220` fixtures
straddle `MIN_BARS`, untouched by this pass). Covers: row count, tag
correctness, hit/RMSE/regime field consistency (`regime` is always
"momentum" or "mean_reversion"), weights saved/reloadable (confirms both
`momentum_head` and `mean_reversion_head` present in the saved state),
naive baseline's absent `hit`/`weights_ref`.

**Real-data validation (Phase 1: `1D`)**: two real checks, since the
first (125 real AAPL bars, the standard small dataset used for every
other trained-from-scratch angle this session) produced only 5 real
steps past the 120-bar floor — all 5 fell into the same "momentum"
regime, not enough real diversity to answer this angle's own core
validation question. Re-ran against 250 real AAPL bars (130 real steps,
110.6s — this angle trains a fresh model per step, meaningfully more
expensive per-step than the single-run angles, hence the larger runtime
for a larger sample) → real regime diversity: 101 momentum, 29
mean_reversion steps. Tags matched standalone `tag_row`. Weights saved
and reloadable — both `momentum_head`/`mean_reversion_head` confirmed
present in the real saved state alongside the shared transformer
encoder. Storage round-trip: zero mismatches. `query_slice`'s
regime-grouped hit-rate/RMSE-component matched a hand aggregation
exactly.

**Real finding — the regime-gating does not clearly earn its keep on
this real sample**: momentum-labeled steps hit 50.5% (n=101),
mean_reversion-labeled steps hit 51.7% (n=29) — essentially
indistinguishable, no real evidence either head specializes usefully
within its claimed regime on this real AAPL data. Overall hit rate
(50.8%) and RMSE (10.19, vs. naive's 3.81) are both unremarkable.
Recorded honestly — this is exactly the kind of real, measured answer
the design doc's own "open/unresolved" section anticipated might come
back either way ("whether the simple autocorrelation-based regime split
is itself a good regime detector is an open, empirical question"), and
on this small-but-real sample, the answer leans toward "not clearly."

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/29-tips_regime_aware_transformer.md` — the decided design, including the paper-vs-code gap analysis.
