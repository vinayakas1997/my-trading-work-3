# DA-40 🟡 Load Full Parquet, Convert All to Dicts

**Component:** `vinu-simulator`
**Files Changed:** `vinu-simulator/vinu_simulator/storage/results.py`, `vinu-simulator/vinu_simulator/service.py`, `vinu-simulator/vinu_simulator/server/routes_read.py`, `vinu-simulator/vinu_simulator/api.py`, `vinu-simulator/vinu_simulator/cli.py`

## Problem

Two wasteful patterns:

### Pattern A: `GET /results/{run_id}/metrics` loads full equity + trades
`get_result()` eagerly loads equity + trades parquet files into memory and converts every row to dicts. The `/metrics` endpoint called `get_result()` but only used `metrics` (from `meta.json`) — equity/trades data was loaded, converted, and **discarded**.

### Pattern B: `load_trades()` double conversion
`load_trades()` did parquet → DataFrame → `itertuples()` → `TradeRecord` objects. Then both `get_result()` and `get_trades()` immediately converted them back to dicts — double the work.

## Audit Scope

Checked all components for similar patterns:
- **vinu-stock-price `query/engine.py`**: `to_dict()` then Python slice — minor, non-1m path already has SQL LIMIT (DA-12 fix)
- **vinu-initial-analysis `compile_dashboard.py`**: `iterrows()` — normal data processing, not wasteful
- **All other components**: no similar "load full data, use only summary" patterns found

DA-40 is the only instance. No other issues to bundle.

## Solution

### 1. Add `load_data` flag to `get_result()`
When `False`, skip loading equity and trades entirely — return only metadata + metrics.

### 2. Add `_trades_to_dicts()` to `ResultStorage`
Load trades directly as dicts (`df.to_dict(orient="records")`) instead of going through `TradeRecord` objects. Updates `get_trades()` to use it.

### 3. Update callers that only need metrics
- `GET /results/{run_id}/metrics` → `get_result(run_id, load_data=False)`
- CLI `metrics` command → `api.get_result(run_id, load_data=False)`

### 4. Update `_run_sync` to support kwargs
Changed from `run_in_executor(None, fn, *args)` to `run_in_executor(None, partial(fn, *args, **kwargs))` so keyword arguments can be passed through async boundaries.

### Files changed

| File | Change |
|------|--------|
| `vinu-simulator/storage/results.py` | Added `_trades_to_dicts()` — dicts directly, no `TradeRecord` intermediate |
| `vinu-simulator/service.py` | `get_result()` accepts `load_data` flag; `get_trades()` uses `_trades_to_dicts()` |
| `vinu-simulator/server/routes_read.py` | `_run_sync()` supports `**kwargs`; `/metrics` passes `load_data=False` |
| `vinu-simulator/api.py` | `get_result()` accepts `load_data` flag, passes through to service |
| `vinu-simulator/cli.py` | `metrics_main()` passes `load_data=False` |

### Verification

1. All 5 files pass syntax check ✓
2. All imports resolve ✓
