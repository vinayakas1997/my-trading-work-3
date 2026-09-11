# Scenario 05 — Multiple correlated positions moving together

## Plan

Written before anything is run. Re-verified against the real code first
(not assumed): `_check_runtime_correlation()` already has thorough
existing unit tests (`TestRuntimeCorrelationMonitor` in
`test_trade_plan_orchestrator.py`) — but every one of them mocks
`_compute_covariance` directly with a hand-built 2x2 numpy matrix. That
proves the *decision logic* (threshold comparison, larger-market-value
side picked, cooldown, reduce_only order) is correct given a correlation
number, but none of them ever exercise the real math that produces that
number: `_compute_covariance` → `dynamic_covariance` (DCC/shrinkage,
`vinu_tools.compute.risk.covariance`) → `correlation_from_covariance`,
fed from real price history fetched over HTTP. That whole pipeline has
never been driven end-to-end in this suite. That is the actual gap this
scenario closes — same spirit as scenarios 01-04 (no LLM, no mock of the
core computation, deterministic engineered data with a known answer).

Also found while designing this: `_compute_covariance`'s own freshness
gate (`min_len < 20 -> return None`) is weaker than what
`dynamic_covariance` itself actually requires internally
(`min_periods = max(window // 2, 10)` = 31 with the default
`_COVARIANCE_WINDOW = 63`, applied to *log returns*, i.e. `n_periods - 1`
must be >= 31 → at least 32 closing prices). Between 20 and 32 bars,
`_compute_covariance`'s own check would pass but `dynamic_covariance`
would silently return an all-NaN matrix, which the `np.any(np.isnan(cov))`
guard then correctly turns into `None` anyway — so the net behavior is
still safe (fails to "unavailable", never to a wrong number), just via a
non-obvious two-layer gate rather than the one gate the code comments
imply. Not a bug (verified: the outer guard catches it), but worth this
scenario using a bar count that comfortably clears both gates (40 bars)
rather than accidentally landing in that dead zone.

Setup — real (not mocked) covariance math, verified numerically before
writing this:
- **AAA / BBB**: two open long positions. AAA's 40-bar price series is a
  trend + oscillation (`100 + 0.5*i + 3*sin(0.7*i)`); BBB's series is
  exactly `0.3 * AAA` at every bar — a pure scale, so its log returns are
  identical to AAA's by construction. Verified with the real
  `dynamic_covariance`/`correlation_from_covariance` pipeline: correlation
  = 0.99999... (effectively 1.0), comfortably over the 0.85 threshold.
  AAA is sized to the larger market value (should be the one reduced).
- **AAA / DDD** (a separate run): AAA unchanged; DDD's 40-bar series is an
  independent, differently-phased oscillation with no shared trend
  (`80 + 2*sin(1.9*i + 1.1) + small alternating drift`). Verified with the
  same real pipeline: correlation = -0.036 — genuinely uncorrelated, not
  just "not proven correlated." Both positions long, so this is the honest
  negative control: real price history that should NOT trip the monitor.
- Full real `cycle()` call in both cases (not a direct
  `_check_runtime_correlation` call) — both positions already open so
  entry is structurally skipped, `_check_runtime_correlation` runs in its
  normal place after the plan loop, fed real HTTP-mocked candle data (the
  same `/candles/{symbol}` endpoint serves both the spot price fetch and
  the historical-returns fetch, same as production).

## Expected Result

1. **AAA/BBB (correlated) run**: `result["correlation_monitor"]["checked"]`
   is `True`, `n_flagged_pairs == 1`, one reduction recorded for AAA (the
   larger market-value side) — a real `reduce_only` order posted, quantity
   cut by the configured `RUNTIME_CORR_REDUCE_PCT` (25% by default), BBB
   left untouched.
2. **AAA/DDD (uncorrelated) run**: `result["correlation_monitor"]["checked"]`
   is `True` (covariance was computable — this isn't the "unavailable"
   no-op path), but `n_flagged_pairs == 0` and no reduction — the real
   math correctly finds nothing dangerous rather than the check simply
   never firing.
3. No exception in either run — `result["status"]` stays `"ok"`.

## Execution Result

Built as `vinu-live/tests/test_pre_live_scenarios.py::TestScenarioMultipleCorrelatedPositions`, 2 tests:

```
tests/test_pre_live_scenarios.py::TestScenarioMultipleCorrelatedPositions::test_real_correlation_math_flags_and_reduces_the_larger_side PASSED
tests/test_pre_live_scenarios.py::TestScenarioMultipleCorrelatedPositions::test_real_uncorrelated_prices_do_not_trip_it PASSED
```

Full `vinu-live` suite after: 312 passed (2 pre-existing, unrelated `test_auth.py` failures — same baseline throughout this audit).

Both runs matched the Expected Result, with one honest wrinkle found while tracing the actual numbers (not a bug — see Reasoning):

- **AAA/BBB**: the real pipeline computed correlation `1.00` (as predicted), flagged the pair, and reduced AAA (the larger market-value side). The *requested* reduce quantity was `2.5` (25% of 10.0 shares), exactly as `RUNTIME_CORR_REDUCE_PCT` specifies. But the book's actual resulting AAA quantity was `7.0`, not `7.5` — traced to `quantize_qty()` (`vinu-live/vinu_live/book/quantize.py`), which rounds every share quantity to the nearest whole share by default (`VINU_LIVE_SHARE_PRECISION=0`, `ROUND_HALF_UP`) before writing it to the book — `2.5` rounds up to `3`, so `10 - 3 = 7`. BBB was untouched at `10.0`, as expected.
- **AAA/DDD**: the real pipeline computed correlation `-0.036` — genuinely uncorrelated, not a "couldn't compute" no-op (`checked: True`). `n_flagged_pairs == 0`, no reduction, both positions unchanged.
- `result["status"]` stayed `"ok"` in both runs.

## Reasoning

This scenario found something real to understand, not something to fix: the end-to-end pipeline (real DCC/shrinkage covariance from real price history → real correlation → threshold comparison → reduce_only order → book write) works correctly, and the previously-untested link in that chain (going from raw price history to a correlation number, rather than a hand-built matrix) produces exactly the number the math predicts. The `7.0` vs `7.5` gap wasn't a bug in `_check_runtime_correlation` — it's the book's own whole-share default rounding, the same rule every other order quantity in this codebase is already subject to (real US equity brokers mostly don't support fractional shares by default either, so this default is the *correct* real-world behavior, not an oversight). It's worth recording here specifically because `RUNTIME_CORR_REDUCE_PCT`'s own name/comment ("reduce by 25%") reads as an exact percentage, and this scenario is what surfaces that the number that actually lands in the book is share-quantized, not the literal fraction — useful to know when reasoning about exact post-reduction exposure, not just "did it reduce."

The negative control matters as much as the positive case here: a monitor that always fires on any two open positions would be useless (or worse, would quietly become "expected noise" that operators learn to ignore). Confirming the real math distinguishes a genuinely uncorrelated pair (`-0.036`) from a genuinely correlated one (`1.00`) — not just that the threshold comparison itself is correct given a number, which was already proven — is what makes this scenario more than a re-statement of the existing unit tests.

## Action Taken

**No fix needed** — the real behavior matched the known-correct answer (the correlation math and the flag/reduce decision), and the one wrinkle found (whole-share rounding on the reduced quantity) is correct, intentional, pre-existing behavior, not something this scenario's scope should change.

No new gaps flagged from this one.
