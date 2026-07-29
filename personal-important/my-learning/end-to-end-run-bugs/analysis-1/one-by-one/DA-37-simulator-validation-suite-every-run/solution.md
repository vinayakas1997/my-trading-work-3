# DA-37 🟠 Simulator Runs Full Validation Suite on Every Run

**Component:** `vinu-simulator`
**Files Changed:** `schemas.py`, `service.py`

## Problem

Every simulation unconditionally runs:
- Monte Carlo permutation (1000 iterations) — shuffles trade PnLs
- Bootstrap Sharpe CI (1000 iterations) — resamples daily returns
- Walk-forward consistency (5 windows)
- Per-symbol attribution (calls `match_trades` a second time — see DA-41)
- Beta regression (per benchmark ticker)
- Regime classification + per-regime performance (per benchmark ticker)

These results are written to `run_card.json`/`run_card.md` on disk and **never returned by any API endpoint**. The `SimulateResponse` and `CustomSimulateResponse` schemas have zero validation/attribution fields. Monte Carlo + Bootstrap alone account for ~95% of the validation cost (~2000 total iterations of array ops).

## Root Cause

Both `simulate()` (line 124) and `simulate_custom()` (line 252) unconditionally called `_run_validation_and_attribution()` and wrote results to disk. There was no parameter to skip validation.

## Solution

Added `run_validation: bool = False` parameter to both `SimulateRequest` and `CustomSimulateRequest`. When `False` (default), the validation suite is skipped entirely. The run card is still written, but without validation/attribution sections.

**Why `False` by default:** Validation results go only to filesystem artifacts (run_card), never surfaced in any API response. Making it opt-in saves significant CPU cycles on every simulation without breaking any contract.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `schemas.py:SimulateRequest` | +1 | Added `run_validation: bool = Field(default=False)` |
| `schemas.py:CustomSimulateRequest` | +1 | Added `run_validation: bool = Field(default=False)` |
| `service.py:simulate()` | 124-144 | Conditional `_run_validation_and_attribution()` + `write_run_card()` only when `req.run_validation` is True |
| `service.py:simulate_custom()` | 252-272 | Same conditional logic |

## Verification

92 simulator tests pass (0 failures). `run_validation` defaults to `False`, so all existing callers automatically skip validation and run faster.

## Future Features

### Expose validation results via API endpoint
- **What:** Add `GET /results/{run_id}/validation` endpoint that returns the Monte Carlo, bootstrap, and walk-forward results from the stored run card.
- **Why:** Currently validation results are only accessible by manually reading filesystem artifacts. An API endpoint would make them queryable by the frontend or research pipeline.
- **Complexity:** Low

### Defer validation to background task
- **What:** Return the simulation result immediately, then enqueue validation work to run asynchronously in the background. Results get appended to the run card when complete.
- **Why:** Eliminates the blocking latency of validation even when `run_validation=True`. The frontend can poll the status.
- **Complexity:** High
