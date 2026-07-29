# DA-21 🟡 `best_result` Is Last Iteration, Not Truly Best

**Component:** `vinu-research`
**Files Changed:** *(pending)*

## Problem

`best_result = result` is set on **every** iteration, **before** the improvement check. If iteration 3 has Sharpe 1.2 but iteration 4 drops to 0.9, `best_result` points to iteration 4 (0.9).

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
