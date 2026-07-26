# Task 2: Exposure Aggregation

**Status:** PENDING

## Purpose

Implement exposure aggregation across the live book: per-symbol, per-cluster (once Phase 2 exists), and portfolio-total.

## Approach

- Per-symbol: current market value = qty * current_price
- Per-cluster: sum of market values for symbols in same shock cluster group
- Portfolio-total: sum of all market values, net exposure
- All aggregations read from positions store

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/book/exposure.py` | — | Created |

## Verification

- [x] Aggregation sums match hand-computed totals across synthetic positions
