# Task 1: Add `_cross_run_comparison()` Method

**Status:** DONE

## Purpose

Add a method to `StrategyResearchLoop` that queries the `research_catalog` for the current symbol's lifetime statistics and returns a STOP or REFINE CriticFeedback when cross-run evidence shows the symbol is unlikely to yield a viable strategy.

## Approach

The `_cross_run_comparison()` method:
1. Reads `self._symbol` and checks `self._storage` is available
2. Calls `self._storage.get_catalog_entry(symbol)` to get lifetime data
3. Checks thresholds:
   - `lifetime_trial_count >= 10` AND `best_sharpe_ever < 0.3` → STOP
   - `lifetime_trial_count >= 5` AND `best_sharpe_ever < 0.1` → STOP
   - `lifetime_trial_count >= 3` AND `best_sharpe_ever < 0.5` → REFINE (with suggestion to pivot)
4. Returns `CriticFeedback` or `None`

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/loop.py` | 1516-1546 | Added `_cross_run_comparison()` method after `_check_mc_gate` |

## Verification

- [x] 407/407 research tests pass
