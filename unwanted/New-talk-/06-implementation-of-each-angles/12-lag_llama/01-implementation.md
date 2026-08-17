---
name: lag_llama-implementation
status: phase-1-done
purpose: the real record of implementing lag_llama's walk-forward backtest against the shared infrastructure.
---

# 12 — lag_llama — Implementation Record

## A note on build order

This angle was originally left "not started (wiring itself deferred, per
its design doc)" in the status table while angles 13/14 were built ahead
of it — a misreading of the design doc. Rereading
`04-enhancement-of-each-angle/12-lag_llama.md` directly: **only the
real-weights path is deferred** (an environment dependency conflict,
tracked as future work in §3/§7). The AR(5) fallback-proxy backtest
itself is fully decided and buildable — it's the *only* code path that
runs today (`model_backend` is always `"fallback_proxy"`, unconditionally,
confirmed from the real `compute.py`). Corrected here, building this
angle now to keep the strict numeric build order honest.

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/lag_llama/compute.py` | Edited | `MIN_OBSERVATIONS` raised 25→100. Extracted `_fit_and_forecast()` — `compute()`'s external behavior unchanged. No trained-model object involved (closed-form AR(5) OLS solve, refit fresh every call) — nothing for a weights store to save, unlike the from-scratch neural angles. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/lag_llama/backtest.py` | New | `lag_llama_step` + `run_lag_llama_backtest` — multi-horizon (5-step), nested `predictions` dict keyed "1".."5" (string keys, same pyarrow-safe convention as Chronos/Kronos), each holding all 5 real quantile levels (p5/p25/p50/p75/p95), `hit` (in [p5,p95]), per-quantile `pinball_loss`, and RMSE/MAE components on the p50 (median) forecast. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/lag_llama/naive_baseline.py` | New | Flat-forecast (`last_close`) naive baseline over the same 5-step horizon, RMSE/MAE only — no CI-coverage/pinball metric, same reasoning as every other naive baseline (a constant forecast has no real band to score). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/_helpers.py` | Edited | Added `pinball_loss(q, forecast, actual)` — the standard quantile proper-scoring-rule, first needed here (per the design doc, "no other angle's real code output is a full multi-level quantile forecast" until this one), placed in the shared helpers module since moirai (next up per the design docs) needs the same function for its narrower 2-level band. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/lag_llama/spec.yaml` | Not touched | Already at the decided 6 `time_formats` from the earlier batch-fix pass. |
| `vinu-initial-analysis/tests/test_lag_llama.py` | Edited | `n=80` → `n=100` in the one test that exercised the full quantile-emission path — broke after `MIN_OBSERVATIONS` was raised to 100, same fix pattern as exponential_smoothing/kalman_filters earlier this session. |
| `vinu-initial-analysis/tests/test_lag_llama_backtest.py` | New | 6 tests. |

## How it was implemented

Group A, multi-horizon like Chronos/Kronos rather than DLinear/lpatchtst's
single-step pattern — nested `predictions` dict, one entry per horizon
step 1-5, each entry holding the model's full real output (not just the
outer band): all 5 quantile levels, in-band hit, per-quantile pinball
loss, and RMSE/MAE components on the median. No weights store: unlike the
trained-from-scratch neural angles, this angle's "model" is a closed-form
5x5 OLS solve refit fresh at every step — there's no persistent state
worth saving as an artifact, and the design doc's storage section never
mentions a `weights_ref`.

`pinball_loss()` is new shared infrastructure, not angle-specific glue —
added to `_helpers.py` rather than inlined in `lag_llama/backtest.py`
since moirai's own decided design (16-moirai.md §3) needs the identical
function for its 2-level (p10/p90) band right after this angle in build
order.

## Testing

6 new tests + 3 pre-existing (1 fixed for the `MIN_OBSERVATIONS` raise,
the other 2 — `no_data`/`insufficient_data` status checks — unaffected).
Covers: row count (caught + fixed a real off-by-one in my own first draft
of the row-count test — the walk-forward step-count formula is
`n - min_observations - horizon + 1`, not `n - min_observations - horizon`,
confirmed against Chronos's own test fixture comment), tag correctness,
nested-dict shape (all 5 horizon steps × all 5 quantile levels + hit +
pinball_loss + RMSE/MAE components present), hit-matches-band-membership
consistency, RMSE/MAE component consistency, no `weights_ref` column,
naive baseline's absent `hit` field.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars
(Alpaca, same dataset as every other Phase-1 `1D` check this session,
reused directly from the lstm angle's cache since no ingest/wiring change
was needed) → 21 rows in 0.03s (the cheapest angle backtested so far by a
wide margin — closed-form OLS vs. every neural/pretrained angle's
gradient descent or transformer forward pass). Tags matched standalone
`tag_row`. Storage round-trip verified: every data column matched
exactly except `quantile_levels`, which round-tripped as a `numpy.ndarray`
instead of the original `list` — confirmed to be a pure parquet-encoding
type artifact (same class of cosmetic difference as lpatchtst's added
metadata columns and lstm's `.equals()` false-negative), not a real data
mismatch, by comparing element-wise content across every row.
`unnest_predictions()` correctly exploded 21 rows × 5 horizon steps into
105 rows, with `horizon` cast back to `int64` (not the raw string dict
key) — `query_slice`'s grouped CI-coverage and RMSE-component numbers by
horizon step showed the expected decay pattern (90%→71% coverage, RMSE
climbing 3.06→10.93 from step 1 to step 5).

**Real finding**: the AR(5) fallback proxy's CI-coverage decays from 90%
(step 1) to 71% (step 5) as horizon grows — the same expected
decay-by-horizon pattern the design doc calls out for Chronos/Kronos,
confirmed real here too, not assumed. RMSE/MAE track very close to the
naive baseline at every step (e.g. step 1: 3.057 vs. 3.198 RMSE; step 5:
10.925 vs. 10.844 RMSE) — this simple AR(5)-on-returns proxy barely beats
"assume no change" on point accuracy, though it does add genuine
probabilistic coverage the naive baseline can't produce at all. Recorded
honestly, consistent with every other angle's real finding this session.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/12-lag_llama.md` — the decided design.
- `../../04-enhancement-of-each-angle/16-moirai.md` — the next angle reusing `pinball_loss()`.
