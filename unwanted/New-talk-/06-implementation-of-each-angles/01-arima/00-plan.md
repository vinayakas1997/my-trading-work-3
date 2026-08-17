---
name: arima-implementation-plan
status: proposed
purpose: what will actually be done to implement ARIMA's walk-forward backtest, and how it will be checked, written before any code is touched — for review before implementation starts.
---

# 01 — ARIMA — Implementation Plan (review before I start coding)

## What the real code looks like today (`angles/arima/compute.py`)

Already read directly, not assumed:
- `_MIN_OBSERVATIONS = 30` (design doc decided 100 — needs raising, same
  move as DLinear's 80→100).
- `_fit_best_arima(close)` grid-searches `(p,d,q)` over a small fixed grid
  by AIC, returns the best fitted `statsmodels` results object + order.
- `compute()` does one fit, forecasts 1 step, returns point forecast + 95%
  CI. No walk-forward loop exists yet — this is a single-shot function
  today, exactly like DLinear's `compute()` was before its backtest wiring.
- `spec.yaml` currently declares only `1D` — the decided design wants all
  6 (`1min, 5min, 15min, 1hr, 4hr, 1day`). This needs updating as part of
  this work (flagged as a known gotcha in `Agents.md`).

## What I will actually do

1. **Refactor `compute.py`** the same shape as DLinear: pull the fit+forecast
   logic into a `_fit_and_forecast(close) -> tuple[dict, ARIMAResults]`
   helper that returns both the result fields *and* the fitted
   `statsmodels` results object. `compute()` keeps calling it internally;
   its external behavior doesn't change. Raise `_MIN_OBSERVATIONS` to 100.
   Unlike DLinear, **no weights store is used here** — ARIMA isn't one of
   the 7 trained-from-scratch angles the weights store was built for
   (DLinear/LSTM/LPatchTST/PatchTST/TFT/iTransformer/TIPS); its `StepResult.weights`
   will always be `None`. What *is* reused across steps is the fitted
   results object itself, via the harness's `state`/`prior_state` — see
   next point.

2. **Write `angles/arima/backtest.py`** with `arima_step` and
   `run_arima_backtest`:
   - On a refit step (`step.is_refit_step`), run the real grid-search fit
     via `_fit_and_forecast`.
   - On a non-refit step (only relevant for 1min/5min, see cadence below),
     reuse `step.prior_state` (the previous step's fitted results object)
     and extend it with the new observation via `statsmodels`'
     `.append(new_obs, refit=False)` instead of re-running the grid search
     — this is the entire reason the harness has `state`/`prior_state` at
     all; ARIMA is the first angle that actually needs it.
   - **Hit definition is CI-coverage**, not direction-match: `hit = 1 if
     lower <= actual_close <= upper else 0` — genuinely different from
     every hit definition written so far (DLinear's was direction-only).
   - `min_observations=100`, `horizon=1` for every timeframe (decided,
     uniform).
   - `refit_cadence`: 1 (refit every step) for `1D/4H/1H`, matching the
     design doc. For `1min/5min` the design doc explicitly leaves the
     actual cadence number **open, pending a real benchmark** — see step 3.

3. **Benchmark real ARIMA fit time before picking `N_1MIN`/`N_5MIN`.**
   The design doc's own "Compute cost caveat" flags the existing
   day-estimate as an unverified guess, not a measurement, and says not to
   trust it as-is. I will time one real grid-search fit (17-order grid) on
   a genuine 100-candle window of real 1-minute data and derive a cadence
   from the actual number, not carry the guess forward.

4. **Naive random-walk baseline** — `angles/arima/naive_baseline.py`
   (small, separate from `arima_step`, sharing the same walk-forward
   harness): `forecast = last_close`, no model, no fit. **One thing this
   needs a decision on, flagging it rather than silently picking**: a
   constant forecast has no natural confidence interval, so "CI-coverage"
   isn't a metric that applies to it the way it does to ARIMA. My proposed
   resolution — score the naive baseline (and ARIMA, for the same
   comparison) on RMSE and directional accuracy, which are well-defined
   for both, and report ARIMA's CI-coverage as its own separate metric
   with nothing to directly compare it against. Tell me if you want it
   done differently (e.g. a rolling-residual-std-based naive CI instead).

5. **Update `spec.yaml`** to declare all 6 decided timeframes.

6. **Unit tests** — `tests/test_arima_backtest.py`, same style as
   `test_dlinear_backtest.py`: row count, tag correctness, CI-coverage hit
   logic on a known-in/known-out example, and specifically a test that the
   non-refit-step path actually reuses `prior_state` instead of refitting
   (the one genuinely new code path this angle introduces).

## How I will check it

Same real-data checklist as DLinear
(`05-storage-enhancement-levels/angle-validation-checklist.md`), but this
is the first angle where it actually has to run across more than one
timeframe:

1. Fetch real data for **all 6 declared timeframes** — daily/4H/1H easily
   via `yfinance`; 1min/5min are limited by provider history windows
   (`yfinance` only keeps ~7 days of 1-minute history), so those two will
   use the shortest real window that still clears `min_observations=100`
   plus a handful of walk-forward steps, not a long window — consistent
   with "small window is fine, must be real."
2. Run the full 7-item checklist independently per timeframe (bar sanity,
   row-count formula, tag spot-check, CI-coverage hit-logic check against
   a hand-computed example, storage round-trip, query-layer hand-check,
   delete-cleanup regression).
3. Specifically verify the refit-cadence path for real: confirm a
   non-refit step's forecast actually came from `.append(refit=False)` on
   the prior state (not a fresh fit) — e.g. by checking the step didn't
   re-run the full order grid search (timing/behavioral check, not just
   "a number came out").
4. Run the naive baseline through the same real data and confirm its
   RMSE/directional-accuracy numbers are sane (worse than or comparable to
   ARIMA's, not a broken constant).
5. Full test suite for both packages, confirming no new failures.
6. Write `01-implementation.md` and `02-real-scenario.md` once all of the
   above passes, and update `../plan.md`'s status table.

## Open items needing your call before/while I implement

- Naive baseline metric choice (step 4 above) — RMSE/directional-accuracy
  as proposed, or something else?
- Everything else above I'm treating as already decided (per
  `04-enhancement-of-each-angle/01-arima.md`) and will just implement.
