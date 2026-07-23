# BUG-02 🟠 alpha158 Indicator Rejected

**Component:** `vinu-research`
**Files Changed:** `vinu-research/vinu_research/tools.py`
**Date Found:** 2026-07-23
**Date Fixed:** 2026-07-23

## Problem

The research loop requested indicators via `tools.py:get_indicators()` but the default
recipe `"pipeline"` returned the alpha158 feature set (which was rejected by the simulator)
instead of simple technical indicators like SMA and RSI. This caused the simulator to
return 422 errors.

## Root Cause

`tools.py:194` used `recipe="pipeline"` as default, which triggered a complex ML-based
feature computation (alpha158). The simulator only supports basic technical indicators
(`sma_20`, `sma_50`, `rsi_14`) and rejected the alpha158 features.

## Suggested Fix

Change the default recipe from `"pipeline"` to a comma-separated list of basic indicators.

## Actual Fix

Changed line 194 in `tools.py` from:
```python
recipe: str = "pipeline",
```
to:
```python
recipe: str = "sma_20,sma_50,rsi_14",
```

## Verification

1. Run research loop with default parameters
2. Confirm simulator returns 200 (not 422)
3. Confirm backtest produces trades with SMA/RSI indicators

## Lessons Learned

- Default recipes should match what the downstream component (simulator) supports
- The `"pipeline"` recipe is for advanced users who understand alpha158
- Always validate indicator compatibility between components
