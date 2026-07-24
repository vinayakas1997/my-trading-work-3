# Phase 3 — Structured Per-Iteration Storage

Status: **not started** · Depends on: Phase 2 (loosely — can be built in parallel) · Blocks: Phase 4

> **Storage design note:** same caveat as [phase-01](phase-01-monte-carlo-foundation.md) — see
> [../02-storage-memory/phase-02-research-simulator-catalog.md](../02-storage-memory/phase-02-research-simulator-catalog.md)
> for a stronger design (resumable per-iteration checkpoints, lifetime trial counts) that this
> phase's `research_iterations` table should likely be built on rather than shipped as a plain
> table first.

## What it is

Persists the *full* iteration-by-iteration history of a research run as structured, queryable
data — not just the winning iteration's code and a flattened markdown report. This is a hard
prerequisite for Stage 2 (Phase 4): the comparative critique agent needs to reason across
*multiple* iterations from *multiple* runs for the same ticker ("what indicator did iteration
3 of a prior run use that this one didn't?"), and that data doesn't durably exist today in a
form a query can reach.

Today, `research_runs` (the SQLite table in
`vinu-research/vinu_research/storage/sqlite_backend.py`, schema at lines ~12-33) stores one row
per *run*: `strategy_code` holds only the *winning* iteration's code, and `report_md` is a
rendered markdown blob (human-readable, not structured). The in-memory `history: list[IterationRecord]`
inside `loop.run()` (`loop.py` line ~171) holds every iteration's code, backtest result, and
critique for the duration of one run, but is discarded (beyond what's baked into
`report_md`) once the run finishes.

## Impact

**Before this phase:** Once a research run completes, everything except the winning
iteration's code and headline metrics is gone as structured data — the only trace of rejected
iterations is prose inside a markdown report. No query can ask "show me every iteration that
tried an RSI-based filter for this ticker."

**After this phase:** Every iteration of every run is a row in a new table, with its code,
metrics, validation result, and critic verdict/suggestions intact and queryable. This doesn't
change any user-facing behavior by itself — it's pure infrastructure — but it's what makes
Phase 4 possible.

**What still won't work after this phase alone:** No comparison logic exists yet; this phase
only makes the data available, it doesn't reason over it.

## Where changes occur

- `vinu-research/vinu_research/storage/sqlite_backend.py`
  - New table `research_iterations`, columns: `id, research_run_id (FK), iteration_number,
    code, backtest_metrics (JSON), validation (JSON), critic_verdict, critic_reasoning,
    suggestions (JSON), created_at`.
  - New write method (e.g. `insert_iteration(...)`) following the existing JSON-serialization
    pattern already used for `metrics`/`config` elsewhere in this file.
  - New read method(s), e.g. `get_iterations_for_run(research_run_id)` and — anticipating
    Phase 4's need — `get_iterations_for_symbol(symbol, exclude_run_id=None)` joining
    `research_iterations` to `research_runs` on `symbol`.

- `vinu-research/vinu_research/loop.py`
  - Inside `loop.run()`'s per-iteration loop, wherever `history.append(...)` currently happens
    (line ~171 area), add a call to persist that same iteration record into
    `research_iterations` via the new storage method — don't just accumulate it in memory.

- `vinu-research/vinu_research/service.py`
  - Extend wherever the research service currently serializes `research_runs` rows for its
    status/report API responses to optionally include the new `research_iterations` rows (or a
    summarized subset), so downstream consumers (Phase 4, and any future UI) can see the full
    trail via the API, not just by querying SQLite directly.

## How to test it

- `vinu-research/tests/` (new or extend existing storage tests): round-trip test —
  insert N iterations for a run via `insert_iteration`, confirm `get_iterations_for_run`
  returns them in order with all fields intact (especially JSON fields: `backtest_metrics`,
  `validation`, `suggestions`).
- Migration test: an existing pre-Phase-3 database (with `research_runs` but no
  `research_iterations` table) gains the new table cleanly on startup, with no data loss to
  existing `research_runs` rows.
- Integration test: run `StrategyResearchLoop.run()` against a mocked backtest/critic and
  confirm the number of rows in `research_iterations` matches the number of iterations actually
  executed (including the case where the loop stops early via `MC_GATE_FAILED` from Phase 2 —
  exactly one iteration row should exist in that case, not zero and not a full budget's worth).
- `get_iterations_for_symbol` test: seed two separate research runs for the same symbol, confirm
  the method returns iterations from both, and that `exclude_run_id` correctly omits the
  current run when passed.
