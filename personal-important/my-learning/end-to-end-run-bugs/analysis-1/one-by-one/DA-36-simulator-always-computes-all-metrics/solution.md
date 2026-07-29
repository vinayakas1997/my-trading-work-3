# DA-36 🟡 Simulator Always Computes All 30+ Metrics

**Component:** `vinu-simulator`
**Files Changed:** *(pending)*

## Problem

`compute_full_metrics()` always calls both `compute_performance_metrics()` AND `compute_extended_metrics()`. The extended metrics (VaR, CVaR, tail ratio, Sharpe CI, beta regression, etc.) are rarely displayed.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
