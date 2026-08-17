---
name: tft-implementation
status: phase-1-done
purpose: the real record of implementing TFT's walk-forward backtest against the shared infrastructure.
---

# 26 — tft — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/tft/compute.py` | Edited | `MIN_BARS` raised 90→100. Extracted `_fit_and_forecast()` (returns the trained model too) — `compute()`'s external behavior unchanged. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/tft/backtest.py` | New | `tft_step` (direction hit on P50 + CI-coverage `in_band` + per-quantile pinball loss via the shared `pinball_loss` + RMSE/MAE + weights save) + `run_tft_backtest`. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/tft/naive_baseline.py` | New | RMSE/MAE-only naive baseline. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/tft/spec.yaml` | Not touched | Already at the decided 6 `time_formats`; already cites the corrected 58.4% benchmark. |
| `vinu-initial-analysis/tests/test_tft_backtest.py` | New | 5 tests. |

## A note on the benchmark citation and cross-check chain

This is the angle whose own design doc closed the citation-cross-check
loop opened by lstm/lpatchtst: it corrected TFT's own figure (58.4%, not
the originally-miscited ~53%) AND checked `itransformer` (angle 09)
against the same benchmark table, confirming no correction was needed
there (`itransformer` cites its own real paper, not the finance-benchmark
survey the other three trained-from-scratch angles were checked
against). Nothing left to verify here — the design doc had already done
this work before implementation reached it.

## How it was implemented

Group A, structurally like DLinear/lpatchtst/patchtst — a fresh model
trained from scratch at every walk-forward step, every step's weights
saved. Architecturally the most distinctive trained-from-scratch angle
in this set: a real variable-selection gate (softmax per-feature
weights), LSTM encoder, self-attention pooling, and a median-plus-
softplus-deltas head construction that **guarantees P10 ≤ P50 ≤ P90 by
construction**, not just empirically — verified directly against the
real TFT paper's component list by the design doc before implementation.

Because the real quantile output is genuinely non-crossing and
probabilistic (not a point forecast with no band, like DLinear/lpatchtst/
patchtst), this backtest reports both `hit` (direction match on P50,
comparable to the corrected 58.4% benchmark) and `in_band` (CI-coverage
on the 80% P10/P90 band, comparable to lag_llama/moirai's own coverage
numbers) — the first angle in the trained-from-scratch set to report
both metric families at once.

## Testing

5 new tests + 3 pre-existing (`n=40`/`n=200` fixtures straddle both the
old and new `MIN_BARS`, unaffected). Covers: row count, tag correctness,
quantile ordering (P10≤P50≤P90 verified on every real backtest row, not
just assumed from the architecture), `in_band` consistency with the
actual band membership, pinball-loss dict shape, weights
saved/reloadable (confirms both `var_select` and `lstm` submodules are
present in the saved state), naive baseline's absent `hit`/`weights_ref`.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars (same
dataset as every other Phase-1 `1D` check this session) → 25 rows in
6.76s. Tags matched standalone `tag_row`. Weights saved and reloadable —
a real trained variable-selection gate + LSTM + attention + dual-head
state (`var_select.gate.0.weight`, `lstm.weight_ih_l0`,
`attn.in_proj_weight`, `median_head.weight`, `delta_head.weight`, and
friends). Storage round-trip: zero column mismatches. `query_slice`'s
grouped hit-rate/coverage-by-day-of-week matched a hand aggregation.

**Real finding**: 36% directional accuracy (P50 vs. actual) on this
real, small (25-step) sample — below the corrected 58.4% paper
benchmark, and below even the naive baseline's implicit 50% coin-flip
reference. CI-coverage (actual inside [P10,P90]) came in at 68%, below
the nominal 80% the band is calibrated for. RMSE (5.08) and MAE (4.10)
both worse than the naive baseline (3.80 / 2.61) on this sample. The
real `variable_selection_weights` output is genuinely informative and
sums to ~1.0 (softmax, confirmed): `vol_5` (0.245) and `ret_1` (0.197)
dominated on this particular real forecast step, `ret_5` (0.112) mattered
least — a real, per-step interpretability signal none of the other
trained-from-scratch angles produce. Recorded plainly, consistent with
every other trained-from-scratch angle's real finding this session on
this particular small sample: the paper's own benchmark universe
(futures, 2010-2025) differs from this project's equity/date range, a
caveat the design doc itself already names.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/26-tft.md` — the decided design, including the benchmark correction and the closed itransformer cross-check.
