---
name: phase-4-test
status: proposed-not-built
purpose: concrete input/expected-output cases proving the one missing endpoint is all that was needed -- ShadowEvaluator's own logic stays untouched and starts working against it.
---

# Phase 4 -- Test plan

**`test_performance_endpoint_returns_real_sharpe_for_known_artifact`**
Input: `GET /agent/broker/performance/{artifact_id}` for an artifact with
real paper-trading fill history.
Expected: `200`, response includes a real computed Sharpe value matching
what `performance_store.py`'s underlying data would produce by direct
computation (assert against an independently-computed expected value, not
just "a number came back").

**`test_performance_endpoint_404s_cleanly_for_unknown_artifact`**
Input: `GET /agent/broker/performance/{artifact_id}` for a nonexistent id.
Expected: `404` with a clear error body -- not a `500`.

**`test_performance_endpoint_signals_insufficient_data_distinctly`**
Input: an artifact that entered `BENCHING` moments ago, with too few
fills to compute a meaningful Sharpe.
Expected: the response explicitly signals "insufficient data" (a distinct
field/status, not a `0` or `null` Sharpe) -- proves the guard rail against
insufficient-data-looking-like-a-bad-result is actually implemented.

**`test_shadow_evaluator_fetch_no_longer_404s`**
Input: `ShadowEvaluator._fetch_paper_sharpe(artifact_id)` called against
the real (now-implemented) endpoint, for a known artifact.
Expected: succeeds, returns a real value -- this is the literal
regression test for the bug this phase fixes; before the fix, this call
404s.

**`test_shadow_evaluator_auto_promotes_within_tolerance`**
Input: a `BENCHING` artifact whose paper-trading Sharpe (from the now-real
endpoint) is within the configured tolerance of its stored backtest
Sharpe.
Expected: the artifact transitions to `ACTIVE` -- proves the existing,
previously-untestable-because-broken promotion logic now actually fires.

**`test_shadow_evaluator_withholds_promotion_outside_tolerance`**
Input: a `BENCHING` artifact whose paper-trading Sharpe degrades
significantly beyond tolerance vs. its backtest Sharpe.
Expected: it does **not** transition to `ACTIVE`. Confirm the exact
real non-promotion behavior (stays `BENCHING`? flags for review?) by
reading `shadow_evaluator.py`'s actual branch for this case before
writing the assertion -- don't assume "stays BENCHING" without checking.

**`test_insufficient_data_neither_promotes_nor_rejects`**
Input: a `BENCHING` artifact where the endpoint reports "insufficient
data" (previous test's case, viewed from `ShadowEvaluator`'s side).
Expected: no status transition happens either direction -- `ShadowEvaluator`
waits for more data rather than treating incomplete history as a verdict.

## End-to-end

**`test_phase4_endpoint_fix_unblocks_existing_gate`**
Input: a `BENCHING` artifact with a full, real fill history sufficient
for a stable Sharpe estimate, run through `ShadowEvaluator`'s existing,
**unmodified** promotion logic against the newly-implemented endpoint.
Expected: the artifact correctly promotes to `ACTIVE` or stays `BENCHING`
per the real tolerance comparison, proving the fix really was just the
missing endpoint -- no change to `shadow_evaluator.py`'s own logic was
needed for the gate to start working.
