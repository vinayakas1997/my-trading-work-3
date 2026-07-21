# DA-47 🟡 CLI Creates 3 DuckDB Connections Per 60s Cycle

**Component:** `vinu-stock-price`
**Files Changed:** *(pending)*

## Problem

CLI continuous mode creates 3 `StockService` instances (and thus 3 DuckDB connections) per polling cycle — `sync_and_backfill()`, `run_cycle()`, and `with StockService()`.

## Root Cause

*(to be filled during discussion)*

## Solution

*(to be filled after implementation)*

## Verification

*(to be filled after implementation)*
