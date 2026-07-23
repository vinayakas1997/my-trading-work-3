# R-A: Hypothesis Identity — Per-Strategy Keying

## Bug

`loop.py:215-217` grabbed `query_by_symbol(symbol)[0]` — the most recently updated hypothesis for that ticker, regardless of strategy type. A "momentum for JPM" run would re-use and mutate a "mean-reversion for JPM" hypothesis created on a previous day. Evidence from unrelated strategies got appended to the same record, `best_sharpe` and `status` contaminated across approaches.

Combined with `hypothesis_registry.py:187-190` (no guard against auto-transitioning a rejected hypothesis back to `validated`), a previously rejected hypothesis could be silently resurrected by a later, unrelated run — leaving `invalidation_reason` populated on a record that now claims to be `validated`.

## Fix

**`loop.py`** — Before reusing an existing hypothesis, normalize both `user_idea` and each candidate's `strategy_type` (lowercase, strip, collapse whitespace). Use the normalized strings for matching. Only reuse a hypothesis if `strategy_type` overlaps with the current `user_idea`. If no match, create a fresh hypothesis for this strategy type.

`_normalize(s)` helper defined locally — `" ".join(s.lower().split())`. Match criteria: exact equality OR one is a substring of the other.

**`hypothesis_registry.py:add_evidence()`** — Added guard before auto-status transitions:
```python
if h.status == HypothesisStatus.rejected:
    LOG.warning("Evidence added to rejected hypothesis %s — status unchanged")
else:
    # existing auto-transition logic
```
Evidence is still appended (for audit trail), but a rejected hypothesis stays rejected.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `loop.py` | 212-234 | Strategy-type matching on hypothesis lookup |
| `hypothesis_registry.py` | 185-195 | Rejected-status guard in `add_evidence()` |
