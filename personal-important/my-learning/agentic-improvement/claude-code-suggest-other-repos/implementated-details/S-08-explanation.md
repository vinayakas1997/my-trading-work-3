# S-08: Decay-Monitoring State Machine — Explanation & Status

## What It Is

A scan method that detects strategy decay and triggers automatic re-research.

## Components

1. **`decay_scan()` method** — added to `vinu_research/scheduled/executor.py`.
   - Scans all artifacts with statuses `ACTIVE` / `MONITORING`
   - For each, checks the latest `DecaySnapshot`
   - If `rolling_sharpe / initial_sharpe < 0.5`, calls `refresh_strategy()` to trigger a full re-research cycle

2. **Store queries used**:
   - `list_artifacts_by_statuses` — finds active/monitoring strategies
   - `get_latest_snapshot` — retrieves the most recent decay snapshot for each artifact

## Wiring

The `decay_scan()` method is **not yet wired** into a scheduler loop. It needs to be called either:
- From `_run_loop` in the scheduler (periodic decay check during normal execution)
- From a separate timer/thread running on a fixed interval (e.g., every N minutes)

## Current Status: ⏸️ UNWIRED

The scan logic is implemented and tested, but there is no caller in the dispatch loop yet. Needs wiring into the scheduler to become active.
