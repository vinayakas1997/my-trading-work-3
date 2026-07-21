# DA-12 🟠 DuckDB Aggregation Done in Python Instead of SQL

**Component:** `vinu-stock-price`
**Files Changed:** `engine.py`

## Problem

The DuckDB query always fetched raw 1m bars from Parquet, then Python:
1. Aggregated them to the requested interval via `aggregate_bars()` (dict loop)
2. Applied price adjustments via `apply_adjusted_prices()` (dict loop)
3. Truncated to `limit` (only after aggregation)

For a 1-year daily query: ~97,500 1m rows fetched from DuckDB, transferred to Python, collapsed into ~250 daily rows. Data transfer was ~390x larger than needed.

## Root Cause

`engine.py:42-77` — single SQL path always fetched deduplicated raw 1m rows. `aggregate_bars()` and `apply_adjusted_prices()` ran in Python dict loops on the full dataset.

## Solution

Two SQL paths in `fetch_candles()`:

**Path 1 — `interval == "1m"`:** Keep current behavior (no aggregation needed). Dedup via QUALIFY, Python-adjusted prices.

**Path 2 — `interval != "1m"`:** Push everything into DuckDB SQL:
- CTE-based dedup (`ROW_NUMBER() OVER PARTITION BY symbol, provider, bar_ts`)
- OHLCV aggregation via `FIRST(open ORDER BY ...)`, `MAX(high)`, `MIN(low)`, `LAST(close ORDER BY ...)`, `SUM(volume)` with `GROUP BY bucket_ts`
- Price adjustment baked into SELECT (`open * COALESCE(adj_factor, 1.0)`)
- `LIMIT` applied in SQL (safe after aggregation)

Also fixed: **no SQL LIMIT** (F3) — the non-1m path now applies LIMIT in SQL, so DuckDB only transfers the requested number of aggregated rows to Python.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `engine.py:15-126` | Full rewrite | Dual SQL paths: raw (1m) vs aggregated (non-1m). Non-1m path pushes dedup + OHLCV aggregation + adj_factor + LIMIT into DuckDB SQL. |

## Verification

33 stock-price tests pass (0 failures). Test `test_candles_5m_aggregate` exercises the non-1m path end-to-end.
