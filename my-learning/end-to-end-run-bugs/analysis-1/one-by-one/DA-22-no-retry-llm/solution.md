# DA-22 🟡 No Retry on Transient LLM Failure in Research

**Component:** `vinu-research`
**Files Changed:** *(pending)*

## Problem

When `asyncio.gather` returns an exception for a candidate, it's logged and skipped — with **no retry**. If 2 of 3 candidates fail, only 1 competes.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
