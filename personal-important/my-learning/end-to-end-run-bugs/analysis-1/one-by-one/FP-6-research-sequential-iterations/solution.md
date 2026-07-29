# FP-6 🟡 Research LLM Calls Are Sequential Across Iterations

**Component:** `vinu-research`
**Files Changed:** *(pending)*

## Problem

The research loop does: generate (parallel candidates) → wait → backtest → wait → critic → wait → repeat. Each iteration fully completes before the next begins. There's no pipelining of iteration N+1's generation with iteration N's backtest.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
