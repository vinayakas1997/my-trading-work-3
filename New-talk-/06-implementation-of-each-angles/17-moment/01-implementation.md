---
name: moment-implementation
status: phase-1-done
purpose: the real record of implementing moment's walk-forward backtest against the shared infrastructure.
---

# 17 — moment — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/moment/compute.py` | Edited | `MIN_OBSERVATIONS` raised 20→100. Extracted `_fit_and_forecast()` — `compute()`'s external behavior unchanged. No trained-model object (closed-form drift/std, no lag-coefficient fit at all — simpler than even moirai's AR(3)) — no weights artifact. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/moment/backtest.py` | New | `moment_step` + `run_moment_backtest` — same shape as moirai's exactly (both proxies emit point + p10/p90), reusing the shared `pinball_loss()`. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/moment/naive_baseline.py` | New | Flat-forecast naive baseline over the 5-step horizon, RMSE/MAE only. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/moment/spec.yaml` | Not touched | Already at the decided 6 `time_formats`. |
| `vinu-initial-analysis/tests/test_moment.py` | Edited | `n=60` → `n=100` — broke after `MIN_OBSERVATIONS` was raised. |
| `vinu-initial-analysis/tests/test_moment_backtest.py` | New | 6 tests. |

## How it was implemented

Group A, multi-horizon, structurally identical to moirai's backtest
(point + 2-level p10/p90 band, no weights store) — the only real
difference from moirai is the underlying fallback method itself: no
lag-coefficient OLS fit at all, just a drift (mean of the last 20
returns) compounded forward with a residual-std-based spread. This is
the angle whose design doc explicitly settles "real-weights wiring will
not be pursued" as a considered no (not deferred, unlike lag_llama/
moirai) — the fallback proxy is still backtested seriously per the
design doc's own reasoning ("worth including in the same cross-angle
comparison... the same way a naive baseline is worth running even though
nobody expects it to win").

## Testing

6 new tests + 3 pre-existing (1 fixed for the `MIN_OBSERVATIONS` raise).
Same coverage shape as moirai/lag_llama's test suites.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars (same
cached dataset as lag_llama/moirai/lstm) → 21 rows in 0.03s. Tags matched
standalone `tag_row`. Storage round-trip: zero column mismatches (same
clean result as moirai's — no list-valued scalar fields to produce the
list-vs-ndarray artifact lag_llama's `quantile_levels` hit).
`unnest_predictions()` correctly exploded 21 rows × 5 horizon steps into
105 rows; `query_slice`'s grouped coverage matched a hand aggregation.

**Real finding**: CI-coverage decays from 86% (step 1) to 67% (step 5),
non-monotonically (62%→67% between steps 4 and 5) — a real, small-sample
artifact worth naming honestly rather than smoothing over: with only 21
real backtest steps, a single flipped hit/miss at the tail can move the
step-5 rate by ~5 points, so this isn't read as "coverage improved at
step 5," just noise at this sample size. RMSE/MAE track close to the
naive baseline, slightly worse at every step on this real sample (e.g.
step 5: 11.906 vs. 10.844 RMSE) — consistent with the design doc's own
expectation that this is "the cheapest and simplest of the three
quantile-emitting fallback angles," not a differentiated performer.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../16-moirai/01-implementation.md` — the angle this one's shape was copied from.
- `../../04-enhancement-of-each-angle/17-moment.md` — the decided design, including the "considered no" on real-weights wiring.
