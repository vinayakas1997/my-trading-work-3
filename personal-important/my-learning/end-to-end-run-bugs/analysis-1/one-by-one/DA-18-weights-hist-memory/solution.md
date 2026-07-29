# DA-18 🟡 `weights_hist` Stored as Python List (3-4× Memory Overhead)

**Component:** `vinu-simulator`
**Files Changed:** *(pending)*

## Problem

The simulation engine accumulates weight history as `weights_hist.append(w.tolist())`. Python `float` objects are ~28 bytes each vs 8 bytes for numpy float64.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
