# DA-6 🟠 ALL API Routes Block ASGI Event Loop

**Component:** `vinu-initial-analysis`
**Files Changed:** *(pending)*

## Problem

Every route handler is `async def` but calls synchronous blocking I/O directly without `run_in_executor`. During a compute pipeline run, ALL other API requests are blocked.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
