# Phase 2 — Catalog + Watermark Pattern for Research/Simulator Storage

Status: **not started** · Depends on: Phase 1 · Blocks: Phase 3

## What it is

Applies the proven stock-price/news pattern — catalog table, incrementally-updated watermark,
resumable job tracking, dedup-on-write — to `vinu-simulator` and `vinu-research`'s results
storage, replacing the current plain key-value design
(`vinu-simulator/vinu_simulator/storage/meta.py`'s `simulation_runs` table,
`vinu-research/vinu_research/storage/sqlite_backend.py`'s `research_runs` table — both "write
a row when a run finishes, nothing tracks completeness or freshness").

This directly supersedes and strengthens the storage work described in
[../01-vision-plan/phase-01-monte-carlo-foundation.md](../01-vision-plan/phase-01-monte-carlo-foundation.md)
(the `validation`/`symbols` columns added there) and
[../01-vision-plan/phase-03-structured-iteration-storage.md](../01-vision-plan/phase-03-structured-iteration-storage.md)
(the `research_iterations` table) — those phases should be re-scoped to build directly on this
folder's Phase 1 (`SQLiteBackend`/`ParquetStore`) and this phase's catalog design, rather than
shipping a bespoke schema first and migrating later.

## Impact

**Before this phase:** A research run or simulation is a write-once event. If
`StrategyResearchLoop.run()` crashes on iteration 4 of 8 (LLM API failure, backtest service
timeout), all prior iteration work is lost — there's no per-iteration watermark the way news
has per-chunk `backfilled_up_to_ts`. There's no way to ask "which symbols haven't been
revalidated recently" without scanning every row. Lifetime trial counts per symbol (needed by
[../01-vision-plan/phase-07-overfitting-and-robustness.md](../01-vision-plan/phase-07-overfitting-and-robustness.md))
require an expensive full scan/join instead of a catalog lookup.

**After this phase:** A crashed research run resumes from its last completed iteration instead
of restarting. "What do we know about symbol X, and how fresh is it" is a single catalog-row
lookup. Lifetime trial counts, last-validated timestamps (needed by
[../01-vision-plan/phase-09-shadow-live-validation.md](../01-vision-plan/phase-09-shadow-live-validation.md)'s
decay detection), and completeness/gap status are all first-class, queryable fields — not
derived by scanning.

## Where changes occur

- New `vinu-research/vinu_research/storage/catalog.py` (or extend `sqlite_backend.py`),
  subclassing `vinu_lib.SQLiteBackend` (Phase 1): a `research_catalog` table, one row per
  symbol, tracking `lifetime_trial_count`, `last_run_id`, `last_run_ts`, `last_validated_ts`
  (watermark), `best_sharpe_ever`, `status` (e.g. `active`/`stale`/`needs_revalidation`).
  Mirrors `vinu-stock-price`'s `symbol_catalog` table shape.
- New `research_jobs`/`iteration_checkpoints` table, keyed `(research_run_id, iteration_number)`,
  idempotent (`INSERT OR IGNORE` pattern from stock-price's `backfill_jobs`), so
  `StrategyResearchLoop.run()` writes a checkpoint after each completed iteration and can resume
  from the last checkpoint on restart rather than from iteration 1. This is the direct fix for
  the "crash mid-loop loses everything" fragility.
- `vinu-research/vinu_research/loop.py` — `run()` checks for an existing incomplete job on
  startup (mirroring `orchestrator.py`'s `_backfill_symbol()` resume check in stock-price) and
  resumes rather than restarting when one exists.
- `vinu-simulator/vinu_simulator/storage/meta.py` and `results.py` — rebuilt on
  `vinu_lib.SQLiteBackend`/`ParquetStore` (Phase 1) with an analogous `simulation_catalog` table
  (per strategy+symbol: `last_run_ts`, `last_validated_ts`, `run_count`) alongside the existing
  per-run `simulation_runs` records — the catalog is a fast-lookup summary layer on top of, not a
  replacement for, per-run detail.
- Dedup-on-write: iteration/trade records use `ParquetStore`'s `dedup_on=[...]` (e.g.
  `dedup_on=["run_id", "iteration_number"]`) so a resumed/retried job never double-writes.

## How to test it

- Unit test: seed a `research_jobs`-style checkpoint table with iterations 1–3 marked complete,
  start `loop.run()` against a mocked backtest/critic, and confirm it begins at iteration 4, not
  iteration 1.
- Unit test: `research_catalog.lifetime_trial_count` correctly accumulates across multiple
  separate research runs for the same symbol (direct input to
  [phase-07](../01-vision-plan/phase-07-overfitting-and-robustness.md)'s family-wise correction).
- Unit test: `last_validated_ts` watermark updates correctly after a successful Stage 0 Monte
  Carlo check, and a query for "symbols not validated in N days" correctly identifies stale
  entries.
- Crash-resume integration test: simulate a mid-loop failure (raise an exception after iteration
  2's checkpoint is written), restart `run()`, and confirm no duplicate iteration rows are
  written and execution resumes at iteration 3.
- Migration test: confirm existing `research_runs`/`simulation_runs` data survives the schema
  upgrade to include the new catalog tables, following the same pre-migration-DB test pattern
  used in [../01-vision-plan/phase-01-monte-carlo-foundation.md](../01-vision-plan/phase-01-monte-carlo-foundation.md).
