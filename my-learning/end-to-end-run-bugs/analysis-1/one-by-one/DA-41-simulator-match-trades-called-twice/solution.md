# DA-41 🟡 Simulator `match_trades` Called Twice

**Component:** `vinu-simulator`
**Files Changed:** *(pending)*

## Problem

In `service.py:run_backtest()`, `match_trades(result.trades)` is called once for the Monte Carlo validation, then `by_symbol_stats(result.trades)` internally calls `match_trades()` again. The matching algorithm is O(n*m).

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
