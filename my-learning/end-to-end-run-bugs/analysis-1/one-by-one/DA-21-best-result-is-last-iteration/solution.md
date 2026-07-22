# DA-21 🟡 best_result Is Last Iteration, Not Truly Best

**Component:** `vinu-research`
**Files Changed:** `loop.py` (2 edits), `tests/test_loop.py` (new test)

## Problem

`best_result` in the research iteration loop always held the **last** iteration's result, not the one with the highest Sharpe ratio. For every REFINE iteration, the code unconditionally overwrote `best_result` without comparing against the previous best.

Example: iterations produce Sharpe ratios [0.8, 1.2, 0.5]. The result with Sharpe 1.2 (iteration 2) should be "best", but it was discarded when iteration 3 (Sharpe 0.5) overwrote it.

## Root Cause

`loop.py:334`: `best_result = result` — unconditional assignment with zero comparison.

## Solution

Wrap both `best_result`/`best_iteration` assignments with a comparison guard:

```python
if best_result is None or result.metrics.sharpe_ratio > best_result.metrics.sharpe_ratio:
    best_result = result
    best_iteration = iteration
```

Applied at 2 locations:
1. **Line 334-335** (REFINE path) — primary fix, every non-PASS iteration now competes
2. **Lines 307-308** (PASS path) — consistency fix, though PASS always breaks immediately

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `loop.py:307-308` | Changed | Added comparison guard in PASS/break path |
| `loop.py:334-335` | Changed | Added comparison guard in REFINE path |
| `tests/test_loop.py` | Added | New `TestBestResultSelection` class with 1 test |

## Test

`test_best_result_is_best_sharpe_not_last`: Creates 3 iterations with Sharpe [0.8, 1.2, 0.5], mocks all external services, and asserts `best_result.metrics.sharpe_ratio == 1.2` and `best_iteration == 2`.

## Verification

44 tests pass (2 pre-existing failures unrelated). The fix ensures `ResearchResult.best_result` actually reflects the best-performing iteration.
