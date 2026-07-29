# BUG-03 🟡 Strategy Code Duplicate Params

**Component:** `vinu-research`
**Files Changed:** `vinu-research/vinu_research/generator.py`
**Date Found:** 2026-07-23
**Date Fixed:** 2026-07-23

## Problem

The LLM-generated strategy code sometimes contained duplicate parameters in the
`__init__` method (e.g., `rsi_period: int = 14` appearing twice). This caused
Python `SyntaxError: duplicate argument in function definition` when the simulator
tried to execute the code.

## Root Cause

`_extract_params()` in `generator.py:426` used a list to track parameters, which
allowed duplicates. When the LLM generated code with the same parameter appearing
multiple times (due to refinement adding new params without removing old ones),
the list preserved both duplicates.

## Suggested Fix

Use `dict.fromkeys()` to deduplicate parameters while preserving order.

## Actual Fix

Changed from list-based tracking to `dict.fromkeys()` with `None` as values:

```python
# Before
params = [(name, default), ...]  # list allowed duplicates

# After
params = list(dict.fromkeys([(name, default), ...]))  # dict deduplicates
```

## Verification

1. Generate strategy code with intentional duplicate params
2. Confirm `_extract_params` returns clean list
3. Confirm simulator can execute the strategy

## Lessons Learned

- Always deduplicate when extracting parameters from generated code
- `dict.fromkeys()` preserves insertion order (Python 3.7+) while removing duplicates
- LLM refinement can introduce parameter drift over multiple iterations
