# Situation 35: total expression-allocation misconfiguration logs too quietly

**Question**: `allocate_signal_scaled`'s expression path
(`_allocate_by_expression`) catches `ExpressionError` per symbol and falls
back to a weight of `0.0`; if every candidate's evaluation fails (e.g. a
typo'd field name in the strategy's YAML `signal` expression), `total <= 0`
and the whole allocation falls back to `allocate_equal`. Is a total
misconfiguration like this distinguishable from a legitimate "no signal
differentiates these symbols today, split evenly" outcome?

**Where**: `vinu-strategy/vinu_strategy/engine/allocation.py::_allocate_by_expression()`.

**How tested**: called the real `run_allocation("signal_scaled", ...)` with
an expression referencing a field name (`made_up_field`) that exists in no
symbol's `signal_context`:

```python
run_allocation("signal_scaled", ["AAPL", "MSFT", "GOOGL"], {}, {"signal": "momentum_score * 2"}, signal_context)
```

**Observed (before fix)**: silently returns a normal-looking equal-weight
`{"AAPL": 0.333, "MSFT": 0.333, "GOOGL": 0.333}` -- correct-shaped output,
real capital gets allocated -- with the only trace of the actual problem
being one `LOG.warning` per symbol per evaluation, at the same severity as
every other soft/expected condition in this file. In a real deployment
running many strategies on a schedule, a config typo like this would run
indefinitely, allocating real capital via a fallback policy nobody chose,
with no operator-visible signal above ordinary log noise.

**Verdict**: **bug found and fixed** (an observability/severity bug, not a
math bug -- the equal-weight fallback itself is a defensible policy choice
for a genuine flat-signal day, same reasoning as `_risk_normalize`'s
cash-floor fallback elsewhere in this package). Bumped the per-symbol
expression-failure log line from `LOG.warning` to `LOG.error` in
`_allocate_by_expression` -- purely a severity change, zero effect on the
actual allocation math, so it doesn't unilaterally decide the harder policy
question (should total-failure reject instead of equal-weight?) the way
`research-discussion-v2`'s reviewed-not-changed findings (#2, #4, #10, #18)
deliberately avoided deciding similar fail-open policy calls on the user's
behalf. Added `test_expression_failure_for_every_candidate_logs_at_error_not_warning`
to `tests/test_allocation.py` (asserts both the allocation output shape AND
an ERROR-level record mentioning the bad field name); confirmed via `git
stash` on just `engine/allocation.py` that it fails (no ERROR record
present) against the pre-fix code, then restored the fix. Full
`vinu-strategy` suite re-run clean after all three of this session's fixes
(pipeline.py, selection.py, allocation.py) -- see situations 33/34.
