# Task 1: Condition Evaluator

**Status:** DONE

## Purpose

Mechanically evaluate a frozen trade plan's `contingency_rules`/`invalidation_conditions`
(metric/operator/threshold triples) against live metric values — the Phase 6 half of Phase 4's
"no free-text instruction requiring interpretation" contract.

## Approach

- `evaluate_condition(value, operator, threshold) -> bool`: the same 6-operator set
  (`>=`, `<=`, `>`, `<`, `==`, `!=`) as `vinu_research.models.ContingencyRule`, reimplemented
  independently (not imported — see design decision #3 in `00-implementation.md`) so
  `vinu-live` never depends on `vinu-research`'s Python package.
- `find_triggered_rules(rules, live_metrics) -> list[dict]`: a rule referencing a metric not
  present in `live_metrics` never triggers — missing data is never treated as satisfying a
  condition, and is logged at debug level, not silently skipped.
- Unknown operators (should never occur if Phase 4's `__post_init__` validation held, but
  `vinu-live` doesn't trust that across a process/service boundary) never trigger, logged as a
  warning.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/trade_plan/condition_evaluator.py` | — | Created |

## Verification

- [x] Tests pass (`tests/test_condition_evaluator.py`, 15 tests)
- [x] Type checks pass
- [x] Manual verification done
- [x] No runtime LLM call introduced outside `vinu-research`
