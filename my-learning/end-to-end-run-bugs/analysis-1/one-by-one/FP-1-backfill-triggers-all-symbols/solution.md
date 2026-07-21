# FP-1 🔴 Backfill Triggers ALL Symbols (Not Just Requested Ticker)

**Component:** `vinu-stock-price`
**Files Changed:**
- `vinu-components/run_pipeline.py`
- `vinu-components/vinu-stock-price/vinu_stock/server/routes_config.py`
- `vinu-components/vinu-stock-price/vinu_stock/service.py`
- `vinu-components/vinu-stock-price/vinu_stock/backfill/orchestrator.py`
- `vinu-components/vinu-stock-price/vinu_stock/storage/parquet.py`

## Problem

`step_stock_price` adds only the requested ticker to the watchlist, then calls `/backfill/trigger` which runs `get_service().run_backfill()` with **no arguments** → `syms = symbols or self.get_watchlist()`. This backfills **every symbol** in the existing watchlist (14+ symbols × 4 years each), not just the requested one. Each pipeline run wastes ~75-83 seconds re-backfilling all watchlist symbols.

## Root Cause

Three issues combine to cause this:

1. **`routes_config.py`** — The `/backfill/trigger` endpoint accepted **no parameters**. No way to scope the backfill to specific symbols.
2. **`service.py`** — `run_backfill(symbols=None)` fell back to `self.get_watchlist()` which returns ALL watchlist symbols. The existing `get_pending_backfill_symbols()` method (which correctly filters to only incomplete symbols) was never wired in.
3. **`orchestrator.py`** — `_backfill_symbol()` had **no completeness guard**. Even if a symbol already had `backfill_status="complete"`, it would unconditionally set it to `"partial"` and re-download every year.

## Solution

### 1. `run_pipeline.py`
Pass `symbols=[ticker]` in the JSON body of the backfill trigger request, limiting it to just the target ticker. Also added a `--force` flag that, when set, passes `force=True` in the body (which triggers re-download via `from_year=2022`).

### 2. `routes_config.py`
- Added `BackfillRequest` Pydantic model with optional `symbols: list[str] | None` and `force: bool` fields.
- Updated `trigger_backfill()` to accept this model via `Body()`.
- When `force=True`, passes `from_year=2022` to bypass the completeness guard.

### 3. `service.py`
Changed the fallback in `run_backfill()` from `self.get_watchlist()` to `self.get_pending_backfill_symbols()`. Now when no symbols are explicitly provided, only symbols with incomplete backfills are processed.

### 4. `orchestrator.py`
- Added `symbols_skipped: int` and `rows_rolled: int` to `BackfillSummary` dataclass.
- Added **completeness guard** at the top of `_backfill_symbol()`: if the symbol already has `backfill_status == "complete"` and no explicit `from_year` was given, skip it entirely.
- Added `rollover_and_consolidate()` called after all symbols finish:
  - `_rollover_previous_years()` — Promotes live data for years < `current_year` into the archive directory and removes the live files.
  - `_consolidate_current_year()` — When daily shard count exceeds `SHARD_CONSOLIDATION_THRESHOLD` (30), consolidates into the base live file.

### 5. `parquet.py`
Added `consolidate_live_shards(live_path)` — reads base + daily shard files, deduplicates, rewrites the base file, and removes the shards.

## Verification

1. **Single-ticker backfill:** Run `python run_pipeline.py --ticker AAPL --from-date 2025-01-01 --to-date 2025-06-01`. Check logs — should only backfill AAPL (not all watchlist symbols).

2. **Completeness skip:** Run the same pipeline again. The completeness guard should skip AAPL entirely. The response summary should show `symbols_skipped=1`.

3. **Force re-backfill:** `python run_pipeline.py --ticker AAPL --from-date 2025-01-01 --to-date 2025-06-01 --force`. Should re-download even if complete.

4. **Fallback to pending:** If pipeline's stock-price step dies before adding to watchlist, the service's `get_pending_backfill_symbols()` fallback ensures only truly pending symbols are processed.

5. **Rollover:** After backfill, check that `live/` files for years < current_year have been moved to `archive/`.

6. **Shard consolidation:** When daily shard count exceeds 30, `consolidate_live_shards()` should merge them into the base file.
