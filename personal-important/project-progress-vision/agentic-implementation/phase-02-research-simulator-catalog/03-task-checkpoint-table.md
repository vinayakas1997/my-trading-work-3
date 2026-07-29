# Task 3: Add Iteration Checkpoints Table + CRUD Methods

**Status:** DONE

## Purpose

Create an `iteration_checkpoints` table keyed on `(run_id, iteration)` so that each iteration within a research run is persisted durably. This enables crash-resume (a restarted run can pick up from its last checkpoint) and provides structured cross-run iteration history for the comparative critique agent (Phase 06).

## Approach

- Table schema: `run_id INTEGER, iteration INTEGER, code TEXT, metrics TEXT (JSON), critic_verdict TEXT, created_at TEXT, PRIMARY KEY (run_id, iteration)`
- Uses idempotent `INSERT OR IGNORE` — if a checkpoint for the same `(run_id, iteration)` already exists, it is not overwritten (prevents duplicate work on resume)
- Methods:
  - `save_checkpoint(run_id, iteration, code, metrics, critic_verdict)` — idempotent insert
  - `get_last_checkpoint(run_id)` — returns the highest iteration number for a run
  - `list_checkpoints(run_id)` — all checkpoints for a run, ordered by iteration
  - `delete_checkpoints(run_id)` — clean up after a run completes

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/storage/sqlite_backend.py` | 292-341 | Added `save_checkpoint`, `get_last_checkpoint`, `list_checkpoints`, `delete_checkpoints` |

## Verification

- [x] `save_checkpoint` inserts checkpoint for a new `(run_id, iteration)`
- [x] `save_checkpoint` does NOT overwrite existing checkpoint (idempotent)
- [x] `get_last_checkpoint` returns the latest iteration
- [x] `list_checkpoints` returns all iterations for a run in order
- [x] `delete_checkpoints` removes all checkpoints for a run
- [x] Checkpoints from different runs are independent
