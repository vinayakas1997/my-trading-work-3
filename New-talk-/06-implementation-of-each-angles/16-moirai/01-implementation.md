---
name: moirai-implementation
status: phase-1-done
purpose: the real record of implementing moirai's walk-forward backtest against the shared infrastructure.
---

# 16 — moirai — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/moirai/compute.py` | Edited | `MIN_OBSERVATIONS` raised 20→100. Extracted `_fit_and_forecast()` — `compute()`'s external behavior unchanged. No trained-model object (closed-form AR(3) OLS, refit fresh every call) — no weights artifact. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/moirai/backtest.py` | New | `moirai_step` + `run_moirai_backtest` — multi-horizon (5-step), nested `predictions` dict keyed "1".."5", each holding the fallback proxy's real 2-level band (p10/p90 — this code only ever computes these two quantile levels, narrower than lag_llama's 5-level band), `hit` (in [p10,p90]), per-quantile `pinball_loss` (reusing the shared `pinball_loss()` added for lag_llama), and RMSE/MAE components on the point forecast. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/moirai/naive_baseline.py` | New | Flat-forecast naive baseline over the same 5-step horizon, RMSE/MAE only. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/moirai/spec.yaml` | Not touched | Already at the decided 6 `time_formats`. |
| `vinu-initial-analysis/tests/test_moirai.py` | Edited | `n=60` → `n=100` — broke after `MIN_OBSERVATIONS` was raised, same fix pattern as every other raised-floor angle. |
| `vinu-initial-analysis/tests/test_moirai_backtest.py` | New | 6 tests. |

## How it was implemented

Group A, multi-horizon like lag_llama (the angle immediately before it in
build order) — same nested `predictions` shape, same "no weights store"
reasoning (closed-form AR(3) solve, nothing to persist). The only real
shape difference from lag_llama: **2 quantile levels (p10/p90), not 5** —
this angle's code genuinely only ever computes an 80% band, not a full
5-level distribution, so `pinball_loss` is applied to exactly the 2 real
levels the model outputs (per the design doc's explicit reasoning:
"using it here on the 2 levels the code actually computes keeps the
metric consistent... rather than dropping it just because this angle
exposes a narrower band"). `pinball_loss()` itself was written once, for
lag_llama, and reused unchanged here — confirming the decision to put it
in `_helpers.py` rather than inline in lag_llama's own module was the
right call.

## Testing

6 new tests + 3 pre-existing (1 fixed for the `MIN_OBSERVATIONS` raise).
Same coverage shape as lag_llama's test suite: row count (formula
confirmed correct on the first try this time, no off-by-one — the lesson
from lag_llama's own test bug carried over), tag correctness, nested-dict
shape (5 horizon steps × the 2 real quantile levels + point + hit +
pinball_loss + RMSE/MAE components), hit-matches-band-membership
consistency, no `weights_ref` column, naive baseline's absent `hit`
field.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars (same
cached dataset as lag_llama/lstm) → 21 rows in 0.02s. Tags matched
standalone `tag_row`. Storage round-trip verified with **zero** column
mismatches this time (lag_llama's own check found one cosmetic
`list`-vs-`ndarray` parquet artifact on `quantile_levels`; moirai has no
equivalent list-valued scalar field, so the round-trip came back byte-for-
byte identical on every shared column). `unnest_predictions()` correctly
exploded 21 rows × 5 horizon steps into 105 rows, `horizon` cast back to
`int64`; `query_slice`'s grouped coverage numbers matched a hand
aggregation.

**Real finding**: CI-coverage decays much faster than lag_llama's —
90%→33% across the 5-step horizon here, vs. lag_llama's 90%→71% on the
identical real data. Two real, structural reasons, not a bug: (1) this
angle's band is nominally 80% (p10/p90) vs. lag_llama's 90% (p5/p95) —
a narrower starting band; (2) AR(3) vs. AR(5) — one fewer lag term,
slightly less signal captured in the point forecast, and critically the
same `sqrt(step) * closes[-1]` spread-growth formula is applied to a
*resid_std* computed from a 3-lag fit, not scaled to actually reach an
80% empirical hit rate by construction — this is a genuine, honestly
reported finding about how mis-calibrated a naively-scaled Gaussian band
gets by horizon step 4-5, not something to "fix" here (the fallback
proxy's math itself, like lag_llama's, isn't in scope to redesign as part
of this backtest-wiring pass). RMSE/MAE track almost exactly the naive
baseline at every step, same finding as lag_llama.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../12-lag_llama/01-implementation.md` — where `pinball_loss()` was first added.
- `../../04-enhancement-of-each-angle/16-moirai.md` — the decided design.
