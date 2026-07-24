# Task 4: Add Gate Check in StrategyResearchLoop

**Status:** DONE

## Purpose

After the first backtest returns, check the validation verdict embedded in the API response. If the MC gate fails, short-circuit with a STOP verdict and appropriate reasoning rather than continuing to refine a strategy that has no statistical edge.

## Approach

1. Add `_check_mc_gate()` method that reads `result.raw["validation"]["verdict"]` — returns a STOP `CriticFeedback` if `passed` is False, or `None` if no validation data or if it passed
2. Call `_check_mc_gate(result)` right after the backtest debug_log and before the benchmark/story/critic section
3. If gate fails, create `IterationRecord`, append to history, call `_on_iteration`, and `break`

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/loop.py` | 318-328 | MC gate check inserted after backtest result |
| `vinu-research/vinu_research/loop.py` | 1498-1513 | `_check_mc_gate()` method added before `_default_risk_critic` |

## Verification

- [x] 401/401 research tests pass
