---
name: chronos-implementation-plan
status: proposed
purpose: what will actually be done to implement Chronos's walk-forward backtest against the shared infrastructure, and how it will be checked, written before any code is touched.
---

# 03 — Chronos — Implementation Plan (review before I start real-data checks)

## What the real code looks like today (`angles/chronos/compute.py`)

Already read directly:
- Currently defaults to `amazon/chronos-t5-tiny` (8M params) — the
  decided design (`04-enhancement-of-each-angle/03-chronos.md` §3)
  upgrades this to `chronos-t5-large` (710M params), a **~90x larger
  model**, explicitly chosen for forecast quality over speed. Only `tiny`
  is downloaded locally right now (confirmed: `data/models/chronos-t5-tiny`
  exists, `chronos-t5-large` does not) — fetching it needs a real
  multi-GB Hugging Face download.
- `MIN_OBSERVATIONS = 30` in code; decided value is a **fixed** context
  requirement of exactly 512 candles (Amazon's stated ceiling for this
  model family, adopted as a hard requirement, not a growing window like
  ARIMA's N=100) — needs raising.
- `context = closes[-512:]`, `PREDICTION_LENGTH = 5`, `num_samples=64` —
  already match the decided horizon; `num_samples=64` is the real
  computational cost driver (64 independent sampling passes through the
  model per forecast call), separate from the checkpoint-size question.
- Real pretrained backend already confirmed working (not fallback) at the
  `tiny` size — this is a genuinely functioning pipeline, not a stub.
- **No GPU in this environment** (checked: `torch.cuda.is_available() ==
  False`). A 710M-param model doing 64-sample generation per call, on
  CPU, is a real, possibly severe cost — this is exactly the "Open/
  unresolved... has not been benchmarked" caveat the design doc itself
  flags (§7), and needs a real measurement before committing to any
  backtest step count, same discipline as ARIMA's refit-cadence benchmark.

## What I will actually do

1. **Benchmark one real `chronos-t5-large` forecast call first**, before
   writing any backtest code — download the checkpoint (real network,
   real multi-GB pull), build a real 512-candle context from already-fetched
   AAPL data, time a single `pipeline.predict(...)` call. This number
   directly determines whether a real walk-forward backtest is feasible
   in this environment/session at all, and if so, how many steps.
2. **Upgrade `compute.py`**: `CHECKPOINT = "amazon/chronos-t5-large"`,
   `MIN_OBSERVATIONS = 512`. Extract the actual forecast call into a
   `_forecast(context) -> dict` helper `backtest.py` reuses, same
   extraction pattern as every other angle so far — `compute()`'s
   external behavior stays otherwise unchanged.
3. **Write `angles/chronos/backtest.py`**:
   - `chronos_step(step) -> StepResult`: one row per step, `row["predictions"]`
     a nested dict keyed `1`-`5`, each holding `p10`/`median`/`p90`/`actual`/`hit`
     — matching the decided nested storage shape exactly (§3-§5), checked
     independently per horizon step against that step's own p10-p90 band.
   - No weights store (nothing is trained — real pretrained weights,
     loaded once, reused every call).
   - `window="expanding"` doesn't apply here either way — Chronos always
     truncates to its own last-512-candles context regardless of how much
     history is handed in, so the harness's window size just needs to be
     `>= 512`; I'll pass a fixed rolling window of exactly 512 to keep
     this explicit and match "adopted as our fixed requirement" literally,
     rather than rely on the model's own internal truncation silently
     doing the same thing.
4. **Naive baseline**: reuse the same `forecast = last_close` idea,
   applied identically to all 5 horizon steps (a flat line), scored via
   RMSE/MAE per step against Chronos's own per-step RMSE/MAE — same
   reasoning as ARIMA's naive baseline (no CI/band-coverage metric for a
   naive forecast, only point-forecast error).
5. **This is the first angle to actually exercise `query.py`'s
   `unnest_predictions`** (per `06-implementation-of-each-angles/plan.md`'s
   build order) — validation must include actually calling
   `unnest_predictions` on real Chronos output and confirming
   `query_slice` on the unnested rows groups correctly by `horizon`, not
   just assume the nested shape "looks right."
6. **Unit tests** — synthetic data, but note: unlike ARIMA/DLinear,
   synthetic *step-level* tests here can't cheaply call the real 710M
   model repeatedly (each call is expensive) — tests will call the real
   `_forecast` helper a small, fixed number of times (2-3 steps max) to
   keep the suite's runtime sane, not loop over dozens of synthetic steps
   the way ARIMA's tests do.

## How I will check it — contingent on step 1's real number

Real-data policy is the same as every other angle (Alpaca, real AAPL
data), but the *scale* of Phase 1 depends entirely on what step 1's
benchmark shows:
- If a single call is fast enough (roughly, comparable to ARIMA's ~0.5s/fit
  order of magnitude) — run a real walk-forward backtest on `1D` (the
  fewest real bars/steps of any declared timeframe) as Phase 1, same
  shape as every other angle's check.
- If a single call is meaningfully slower (multi-second to tens-of-seconds
  range) — Phase 1 still happens on real data, but with a **deliberately
  small number of real steps** (e.g. 3-5, not a full 25-step `1D` backtest)
  — enough to prove the architecture (tagging, nested storage, unnest,
  query, naive comparison) genuinely works end-to-end on real output,
  without spending an impractical amount of session time computing dozens
  of real 710M-param forecasts. This would be recorded honestly as a
  smaller-than-usual Phase 1, not hidden.
- Either way: bar sanity, tag spot-check, nested-predictions structure
  check, `unnest_predictions` + `query_slice` check, storage round-trip,
  naive comparison, full test suite — same checklist items as every
  other angle, just possibly fewer real steps feeding them.

## Open items

None needing your call before I start the benchmark — proceeding straight
to step 1 (the real timing measurement), since that number is what
determines the rest of this plan's shape, not a preference decision.
