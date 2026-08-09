---
name: arima-implementation
status: done
purpose: the real record of implementing ARIMA's walk-forward backtest against the shared infrastructure — files touched, how it was built, how it was tested, and every bug actually found (with fix number), kept up to date as the work happens, not written after the fact.
---

# 01 — ARIMA — Implementation Record

## Status as of this update

Code, tests, and architecture (compute → backtest → storage write → storage
read-back → query) are done. Real-data validation is done for **all 6
declared timeframes** — the two-phase policy (`Agents.md`'s "Two-phase
timeframe checking," coarsest-first, defer the rest) was decided partway
through this angle's work specifically because ARIMA's own runtimes are
expensive, but the `5min`/`1min` background run that was already in
flight at that point finished on its own shortly after, so this angle
ended up with full coverage anyway rather than artificially deferred —
recorded as such below, not split into a fake phase-1/phase-2 for an
angle that's actually fully checked. Later angles will genuinely use the
two-phase split where it's needed.

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/arima/compute.py` | Edited | Split into `_forecast_fields()` + `_fit_and_forecast()` (returns the fitted `statsmodels` results object, not just the output dict) + `compute()` (unchanged external behavior, now calls the helpers). `_MIN_OBSERVATIONS` raised 30→100. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/arima/backtest.py` | New | `arima_step` (CI-coverage hit definition, refit-cadence-aware via `state`/`prior_state`) + `run_arima_backtest`. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/arima/naive_baseline.py` | New | Naive random-walk baseline (`forecast = last_close`) through the same harness, for the "does ARIMA beat doing nothing" comparison the design doc calls for. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/arima/spec.yaml` | Edited | `time_formats` widened from `[1D]` to the 6 decided timeframes (`1min, 5min, 15min, 1H, 4H, 1D`). |
| `vinu-initial-analysis/tests/test_arima_backtest.py` | New | 8 tests — see "Testing". |
| `06-implementation-of-each-angles/01-arima/00-plan.md` | New | Pre-implementation plan (written and reviewed before any code, per the established discuss-first process). |

## How it was implemented

Same shape as DLinear's glue code, plus two things DLinear didn't need:

1. **CI-coverage hit definition**: `hit = 1 if lower <= actual_close <= upper else 0`, using ARIMA's own 95% confidence interval — not a direction-match like DLinear.
2. **Refit-cadence via `state`/`prior_state`**: on a refit step, `arima_step` runs the real AIC grid search (`_fit_and_forecast`). On a non-refit step, it extends the *previous* step's fitted `statsmodels` results object with `.append([new_obs], refit=False)` instead of re-fitting — confirmed via a real benchmark that this is ~170x cheaper per step (0.53s full grid-search fit vs. 0.003s append-only, both on a real 100-candle window). `REFIT_CADENCE` is 1 (refit every step) for `1H/4H/1D` per the decided design, and "~once per hour of market time" (60/12/4 steps) for `1min/5min/15min` — the 15min number isn't explicitly named in the design doc's `N_1MIN/N_5MIN/N_1H/N_4H/N_1D` list, so this extends the same rule to fill that gap rather than leaving it undecided.

No weights store is used — ARIMA doesn't train a neural net; `StepResult.weights` is always `None`.

## Testing

8 new tests in `tests/test_arima_backtest.py`, synthetic data (fast,
deterministic), covering: row count, tag correctness, CI-coverage hit
logic against a hand-computed check, absence of `weights_ref`, that 1D
(cadence=1) refits every single step (verified by counting real calls to
`_fit_best_arima` via monkeypatch), that 1min (cadence=60) actually skips
most refits and reuses `prior_state` instead, and the naive baseline's
forecast/error fields. All 8 pass (~24s — real ARIMA fits, not mocked).
The 5 pre-existing `test_arima.py` tests still pass unchanged, confirming
the `compute.py` refactor didn't change `compute()`'s external behavior.

**Full `vinu-initial-analysis` suite**: 223 passed (up from 215 pre-ARIMA
— the 8 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` `KeyError: 'bar_ts'` failures
(confirmed unrelated in `05-storage-enhancement-levels/implementation-summary.md`),
no new failures. `vinu-tools`: 127 passed, unaffected (no changes there).

**Real-data validation** — Alpaca (not synthetic, not `yfinance`), ~6
months, AAPL, 1-minute bars aggregated to every other timeframe via the
real `vinu_stock.query.aggregate.aggregate_bars` (see
`Agents.md`/"Real data source and validation window"):

| Timeframe | Real bars | Backtest rows | Runtime | CI-coverage (nominal 95%) |
|---|---|---|---|---|
| 1D | 125 | 25 | 14.7s | 80.0% |
| 4H | 321 | 221 | 106.7s | 90.5% |
| 1H | 1011 | 911 | 421.2s | 93.0% |
| 15min | 3659 | 3559 | 459.2s | 93.6% |
| 5min | 10431 | 10331 | 469.5s | 93.2% |
| 1min | 49757 | 49657 | 658.5s | 88.8% |

All 6 CI-coverage numbers land in a plausible band below the 95% nominal
level — mildly overconfident intervals across the board, consistent
across timeframes rather than one outlier, which reads as a genuine
property of how this ARIMA setup estimates its intervals rather than a
per-timeframe bug. `1min`'s runtime (658.5s) being the longest, not
`5min`'s, matches what the refit-cadence design predicts: both are tuned
to refit about once per hour of market time, so their *refit* counts are
close, and the difference comes from `1min` having ~5x more cheap
`append(refit=False)` steps — exactly the smaller, additive effect
expected, not a surprise.

**Architecture proof (separate from whether ARIMA's forecasts are good)**:
for 1D/4H/1H, each real result set was written through the real
`AngleStorage`, read back with an exact row-count match, queried with a
real `query_slice` grouping that matched a hand-computed pandas `groupby`
exactly, and `RunLog.get_latest_run()` correctly resolved each
timeframe's own latest run without cross-timeframe collision. Full
details/commands in `02-real-scenario.md`.

**Naive baseline comparison (1D/4H/1H)**: ARIMA did **not** beat the naive
random-walk baseline on RMSE/MAE on any of the three — naive's error was
consistently slightly lower. Recorded as a real, honest result (exactly
the outcome the design doc's own rationale flagged as a real possibility
for a price series close to a random walk), not something to explain away.

## Bugs found and fixed

**Bug 1 — Alpaca API rejects Python's default ISO timestamp format.**
`datetime.isoformat()` includes a `+00:00` timezone offset; Alpaca's
`start`/`end` query params need `%Y-%m-%dT%H:%M:%SZ` instead, or the
request 400s. Found on the very first real connectivity test, before any
angle code was touched.
**Fix 1**: use `strftime("%Y-%m-%dT%H:%M:%SZ")` for every Alpaca request.

**Bug 2 — walk-forward loop was using an expanding window, not the
decided "rolling" window.** `run_arima_backtest`/`run_naive_baseline`
called `run_walk_forward` without an explicit `window=`, so it silently
used the harness's `"expanding"` default. Two problems: (a) the decided
design (`04-enhancement-of-each-angle/01-arima.md`) explicitly says
"rolling refit," not expanding; (b) an expanding window means every
step's fit operates on more data than the last, so cost keeps growing
through the backtest instead of staying flat — this is *why* the first
real 1H run took 1051s (17.5 min) instead of the ~7 min a flat-cost
estimate predicted. Found by comparing real measured runtime against the
benchmark-predicted estimate and noticing the mismatch, not by inspection.
**Fix 2**: pass `window=MIN_OBSERVATIONS` (a fixed 100-candle rolling
window) explicitly in both `run_arima_backtest` and `run_naive_baseline`.
Re-running 1H after the fix: 421.2s — 2.5x faster, and now matches the
decided design's own wording.

**Bug 3 (design gap, not a code bug) — naive baseline's originally
proposed metric (directional accuracy) doesn't apply to a "no change"
forecast.** A constant forecast is always "flat," so a direction-hit-rate
comparison against it isn't measuring anything real — it would just
report the naive model as wrong every time the market actually moved.
Caught while implementing `naive_baseline.py`, before writing any test
against it, by asking what "hit" would even mean for `forecast ==
last_close`.
**Fix 3**: naive baseline reports RMSE/MAE only (directly comparable to
`arima_step`'s own `abs_error`/`squared_error` fields, added for this
purpose); no direction or CI-coverage metric is reported for it, since
neither has a meaningful naive-baseline equivalent.

**Bug 4 (shared infrastructure, not ARIMA-specific) — the `trigger` HTTP
endpoint never actually restricted computation to the requested
granularity.** `routes_v1.py`'s `POST /trigger/{ticker}/{granularity}/.../{method}`
validated `{granularity}` but — per its own module docstring — never
threaded it through to computation; triggering any angle ran it across
*every* timeframe in that angle's `spec.yaml`, not just the one requested
in the URL, and `AngleRunner`/`RunLog` always wrote/recorded under the
storage default `granularity="1D"` regardless of what was actually
computed. Invisible while every angle declared only `1D` (one timeframe,
so "every declared timeframe" and "the one requested" were the same
thing); surfaced once angles started declaring 6 — `test_api_v1.py::test_trigger_and_poll_flow`
started failing because triggering `garch` (now 6 timeframes) took 6x as
long against the (not running in this environment) local price service,
blowing the test's 30s poll deadline. Found by tracing exactly why a
previously-passing test broke, not assumed to be flaky.
**Fix 4**: added an opt-in `time_format` parameter threaded through
`AngleRunner.run()` → `_run_angle()` → `CorrelationAPI.compute_and_store()`
→ `InitialAnalysisService.run_analysis()` → `routes_v1.py`'s `trigger`
handler. When given, `_run_angle` computes only that one time_format
(raising `ValueError`, reported as a per-angle `"error"` status, if the
angle doesn't declare it) and writes/records it under that exact
`granularity` instead of the default. `None` (every other existing call
site, e.g. the tier2 scheduler) preserves the prior behavior exactly —
this was an additive, opt-in fix, not a behavior change for anything
already working. 4 new tests in `tests/test_runner_time_format.py` cover
all of it directly against a real temporary fake angle package (not
mocked): unrestricted runs still compute every declared format, a
restricted run computes only the requested one and writes under its
granularity, an undeclared format is rejected, and — checked directly via
the fake angle's own call log — the restricted run never even invokes
`compute()` for the format it wasn't asked for. Full suite after the fix:
227 passed (up from 223), same 11 pre-existing unrelated failures, no new
ones, and the specific test that broke now passes again.

## Related files

- `02-real-scenario.md` — the real example (input data, calls, output,
  storage/query round-trip) proving this works.
- `00-plan.md` — the pre-implementation plan this followed.
- `../plan.md` — the overall implementation plan and status table.
- `../Agents.md` — "Real data source and validation window" section,
  which this implementation follows.
- `../../04-enhancement-of-each-angle/01-arima.md` — the decided design.
