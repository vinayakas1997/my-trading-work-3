# DA-9 🟠 LLM Refinement Failure Generates Fresh Template Strategy

**Component:** `vinu-research`
**Files Changed:** `loop.py`, `test_loop.py`

## Problem

When LLM refinement returned empty candidates (transient failure), the fallback code at `loop.py:776` called `generate_strategy(recipe=...)` producing a **completely new template strategy** unrelated to the previous code. Critique lines were then injected into this foreign template — meaningless modifications that often caused `NameError` at runtime.

## Root Cause

Lines 776-778: `recipe = find_recipe(user_idea); code = generate_strategy(...)` — always generated fresh, with no check for `previous_code`.

## Solution

Changed the fallback block to check `llm_available and previous_code` before deciding:

```python
if llm_available and previous_code:
    # LLM was tried but returned nothing — reuse previous code
    code = previous_code
else:
    # Template mode, or first iteration — generate from recipe
    recipe = find_recipe(user_idea)
    code = generate_strategy(recipe=recipe, user_description=user_idea)
```

The `llm_available` guard preserves the existing `generator_mode="template"` behavior (fresh template every iteration), while `llm_available=True + previous_code` correctly handles the LLM-failure-to-previous-code case.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `loop.py:776-784` | ~8 | Conditional fallback to `previous_code` when LLM was tried but failed |
| `test_loop.py:608-610` | ~3 | Updated test assertion: expect `previous_code` instead of fresh template |

## Verification

369 tests pass (1 pre-existing config env var failure).

## Future Features / Open Questions

During analysis of this issue, the following feature gaps were identified:

### 1. `user_idea=None` validation gap in `run_research`
- **What:** `service.run_research()` expects `user_idea: str` (required), but the API schema (`RunResearchRequest`) allows `None`. If `None` passes through, the LLM generator gets `None` as the idea — undefined behavior. `ensure_strategy()` handles this correctly (auto-proposes from angles), but `run_research()` doesn't.
- **Where:** `service.py:57-68`
- **Complexity:** Low

### 2. Explicit "not worth pursuing" conclusion in report
- **What:** The research report shows metrics and verdicts but never explicitly states "this strategy is not suitable for this stock." A clear conclusion at the top of the report would help callers decide.
- **Where:** `report.py:15-335`
- **Complexity:** Low

### 3. Multi-stock strategy exploration
- **What:** Automatically try a strategy idea on multiple candidate stocks and rank by Sharpe/deflated Sharpe. The `universe` parameter exists but requires manual stock selection.
- **Where:** `loop.py:151`, `service.py:57-182`
- **Complexity:** Medium

### 4. Strategy-stock fit assessment
- **What:** Evaluate whether a strategy's signal types (momentum, mean-reversion, breakout) align with the stock's characteristics (trending, range-bound, volatile, high/low beta).
- **Where:** New component or module
- **Complexity:** High

### 5. Auto-suggest alternative stocks on validation failure
- **What:** When a strategy fails all validation for a stock, suggest alternative stocks where the same idea might work better based on signal-stock fit.
- **Where:** `service.py:57-182`, `report.py`
- **Complexity:** High
