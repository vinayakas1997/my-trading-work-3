# DA-17 🟡 No Caching of Simulation Results for Identical Inputs

**Component:** `vinu-simulator`, `vinu-initial-analysis`
**Files Changed:** `vinu_simulator/storage/meta.py`, `vinu_simulator/service.py`, `vinu_initial_analysis/runner.py`, `vinu_initial_analysis/storage/meta.py`

## Problem

- `simulate()` and `simulate_custom()` run the full pipeline every time with no content-addressed cache
- `vinu-initial-analysis` `_run_angle()` re-computes angles for the same symbol+date range on every request

## Root Cause

Neither component checked for existing results before running.

## Solution

### vinu-simulator

1. **Schema:** Added `config_hash` TEXT column to `simulation_runs` table via `_ensure_config_hash_column()`. Added `config_hash` param to `insert_run()` and `get_run_by_config_hash()` in `MetaStorage`.

2. **Hash computation:** `_compute_config_hash()` in `service.py` builds a canonical JSON dict of all simulation params, then SHA-256 hashes it.

3. **Cache check:** Both `simulate()` and `simulate_custom()` compute `config_hash` early and call `get_run_by_config_hash()` before any expensive work. On cache hit, `_reconstruct_result()` loads equity + trades from parquet storage and rebuilds a `SimulationResult`.

4. **Store hash:** Both methods pass `config_hash=config_hash` to `insert_run()` on new runs.

### vinu-initial-analysis

1. **RunLog query:** Added `has_existing_run()` to `RunLog` — checks for a completed run matching symbol + angle_name + analysis_from + analysis_until (ISO string comparison).

2. **Skip path:** `_run_angle()` checks `has_existing_run()` before importing or computing; logs "Skipping" and returns 0 rows if a cached run exists.

## Verification

- Syntax confirmed: `python -c "import ast; ast.parse(open(...))"` passes for both components.
- Manual test: Call `simulate()` twice with same inputs → first call runs full pipeline, second call returns cached result instantly.
- Manual test: Call `run_analysis()` twice for same symbol → second call skips all angles.
