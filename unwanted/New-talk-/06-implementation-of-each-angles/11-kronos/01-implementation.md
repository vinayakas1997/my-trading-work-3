---
name: kronos-implementation
status: phase-1-done
purpose: the real record of implementing Kronos's walk-forward backtest against the shared infrastructure.
---

# 11 — kronos — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/kronos/compute.py` | Edited | Extracted `_fit_and_forecast()` (real predictor call + fallback MLP path preserved intact) — `compute()`'s external behavior unchanged. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/kronos/backtest.py` | New | `kronos_step` (nested `predictions`, string-keyed from the start — see below) + `run_kronos_backtest`, `WALK_FORWARD_MIN_OBSERVATIONS = 512`. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/kronos/naive_baseline.py` | New | Same RMSE-per-horizon-step pattern as Chronos's. |
| `vinu-initial-analysis/tests/test_kronos_backtest.py` | New | 6 tests. |

`spec.yaml` was already at the decided 6 timeframes.

## How it was implemented

Group A, structurally like Chronos: real pretrained weights
(`NeoQuasar/Kronos-base`, 102.3M params — already downloaded locally,
confirmed before starting), a genuine 5-step full-OHLC forecast, nested
`predictions` storage. No weights store — nothing is trained.

**One real gap in the code's own constants, found before writing any
backtest code**: `compute.py`'s `MIN_OBSERVATIONS = 30` /
`CONTEXT_WINDOW = 32` only ever gate the **fallback** MLP path — the real
Kronos predictor's actual context requirement is the hardcoded
`KronosPredictor(..., max_context=512)`, a completely different number
those two constants have nothing to do with. Per the decided design
("512, same treatment as Chronos"), the walk-forward harness's own
`min_observations` is set to `512` directly in `backtest.py`
(`WALK_FORWARD_MIN_OBSERVATIONS`), not derived from the code's existing
(fallback-path-only) constants.

**Applied Chronos's own found-bug fix from the start, not rediscovered**:
`predictions` dict keys are strings (`"1"`-`"5"`), not ints — pyarrow/
parquet rejects non-str/bytes dict keys, a real bug Chronos's
implementation found the hard way (03-chronos/01-implementation.md Bug
2). Kronos is the second nested-predictions angle, so this was written
correctly the first time instead of re-discovering the same failure.

## Real cost — measured, matching Chronos's category

Benchmarked directly: ~5.2s/call warm (~7.5s cold, one-time model load,
cached after — the weights were already downloaded locally before this
work started). Same cost class as Chronos, no incremental-refit path
(pretrained transformer, nothing to partially update). Same conclusion
as Chronos: Phase 1 uses a small, deliberately-limited real slice, not a
full-scale backtest.

## Testing

6 new tests, real model calls kept to a minimum (module-scoped fixture,
2 real steps, reused across 5 assertion tests) — same pattern as
Chronos's test suite, for the same reason (real 102M-param model calls
are too expensive to loop dozens of times in a unit test). All 6 pass
(~12.8s).

**Real-data validation**: same real 1H AAPL data as Chronos (`1D`
infeasible — only 125 real daily bars available, far short of 512).
Deliberately small real slice (525 bars → 9 real steps, matching
Chronos's scale exactly for a fair side-by-side). Real output: full OHLC
forecast per horizon step, real hits/misses, real `close_sq_error`
values. Storage round-trip and `unnest_predictions`/`query_slice` both
verified exactly against a hand pandas `groupby` on real Kronos output.

**Real finding**: naive beat Kronos on RMSE at every horizon step (same
pattern as ARIMA/Chronos/exponential_smoothing/iTransformer — only
`kalman_filters` has beaten naive so far this session). Naive's RMSE
values here are identical to Chronos's naive-baseline numbers, since both
ran on the exact same real 1H window with the same deterministic
forecast-last-close step function — a real, useful cross-check that
nothing broke in the shared harness between the two angles.

**Full `vinu-initial-analysis` suite**: 278 passed (up from 272
pre-this-angle — the 6 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures, no new failures.

## Related files

- `02-real-scenario.md` — the real example.
- `00-plan.md` — the pre-implementation plan.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/11-kronos.md` — the decided design.
