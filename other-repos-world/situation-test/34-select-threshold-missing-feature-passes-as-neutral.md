# Situation 34: threshold selection treats a missing feature as a real 0.0

**Question**: `select_threshold`'s named-field branch reads
`features.get(field, 0.0)` when checking a symbol against `min_val`. What
happens when a symbol's `signal_context` genuinely has no entry for that
field at all (a partial upstream features-API response, or an indicator not
yet computable for a thinly-traded/newly-listed symbol) rather than a real
computed `0.0`?

**Where**: `vinu-strategy/vinu_strategy/engine/selection.py::select_threshold()`,
feeding into `allocation.py::allocate_equal()` downstream.

**How tested**: called the real `run_selection("threshold", ...)` with one
symbol (GOOGL) whose `signal_context[sym]["features"]` dict is present but
empty -- exactly what `service.py::_extract_feature_values()` produces
whenever the features API responds for a symbol but omits one specific
requested indicator (confirmed by reading `_extract_feature_values`, which
already defaults *any* missing indicator name to `0.0` when building that
dict -- so an empty/partial `features` dict for a live symbol is a real,
reachable shape, not a hypothetical one):

```python
signals = {"AAPL": 1.5, "GOOGL": 0.3}
signal_context = {
    "AAPL": {"features": {"MOM_20": 1.5}},
    "GOOGL": {"features": {}},
}
run_selection("threshold", [], signals, {"on": "MOM_20", "min": -0.2}, signal_context)
```

**Observed (before fix)**: `["AAPL", "GOOGL"]` -- GOOGL, which has *no*
computed MOM_20 value at all, is selected anyway because the missing key
silently defaults to `0.0`, and `0.0 >= -0.2`. Chained into `allocate_equal`
(the default allocation method), GOOGL then receives a full, real equal
share of capital in a strategy explicitly designed to filter out symbols
that don't clear a momentum bar -- purely because of a data gap, not because
it actually cleared anything. Any `threshold` selection with a negative
`min` is vulnerable to this; a `min >= 0` selection happens to be safe only
by coincidence (a genuinely-absent value can't beat a non-negative bar via
a `0.0` stand-in... except when `min == 0.0` exactly, where it can).

**Verdict**: **bug found and fixed**. Changed `select_threshold` so a field
that's entirely absent from `features` excludes the symbol outright, rather
than substituting `0.0` and running it through the threshold comparison.
Re-ran the exact repro post-fix: returns `["AAPL"]` only. Added
`test_select_threshold_excludes_symbol_missing_the_field_entirely` to
`tests/test_selection.py`; confirmed via `git stash` on just
`engine/selection.py` that this test fails (`['AAPL', 'GOOGL'] != ['AAPL']`)
against the pre-fix code, then restored the fix. Full
`test_selection.py`/`test_pipeline.py`/`test_risk.py`/`test_allocation.py`
suite: 37/37 pass (36 pre-existing + 1 new).

Same root pattern as situation 31 (a repeatable "no real data" condition
silently standing in for a real value that then drives a downstream
decision) and situation 33 (found in the same file this session) -- a third
confirmation that `vinu-strategy`'s own engine internals were genuinely
unaudited by the prior `research-discussion-v2` pass.
