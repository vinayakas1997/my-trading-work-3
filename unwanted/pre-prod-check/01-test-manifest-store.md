---
name: test-manifest-store
status: planning only — not yet implemented
---

# Task: build the test manifest store

## Goal

A small, standalone SQLite store that records one row per
`(test_run_id, ticker, stage)` combination as the pre-prod harness
exercises the pipeline, so progress survives a crash, a killed process,
or a move to a different machine.

## Why

Without this, "did we already verify AAPL through `risk_gatekeeper`?" has
no answer except re-reading logs by hand, and a machine restart mid-pass
means starting the whole check over. `TickerLedger` already solved this
exact problem for production events (append-only, one row per
ticker-relevant event, `ref_id` pointing back to the real record) — this
reuses that pattern rather than inventing a second one.

## Where it lives

Recommend `vinu-components/testing/pre_prod_manifest.py` (or wherever the
implementing agent finds the project's convention for cross-package
tooling lives — check `vinu-infra/` for shared-store precedent first,
since `TickerLedger` and `HypothesisRegistry` both live under
package-specific `store.py` modules, not a single central location).

## Schema

```
test_manifest(
    id INTEGER PRIMARY KEY,
    test_run_id TEXT NOT NULL,      -- groups one full pass (e.g. a UUID or date-stamped label)
    ticker TEXT NOT NULL,
    stage TEXT NOT NULL,            -- see task 02 for the fixed stage vocabulary
    status TEXT NOT NULL,           -- 'pending' | 'pass' | 'fail'
    timestamp TEXT NOT NULL,        -- ISO 8601, when this row was last written
    evidence_ref TEXT,              -- pointer into the real store this stage wrote to
                                     -- (artifact_id, run_id, hypothesis id, TickerLedger row id — whatever's real)
    notes TEXT,                     -- free text: what specifically was checked / what failed
    UNIQUE(test_run_id, ticker, stage)
)
```

`UNIQUE(test_run_id, ticker, stage)` is what makes resume-by-upsert work
— re-running the harness for a ticker/stage pair that's already `pass`
should either skip it outright or overwrite the same row, never duplicate
it.

## Steps

1. Create the store module with `init_db()`, `record(test_run_id, ticker,
   stage, status, evidence_ref=None, notes=None)` (upsert semantics), and
   `get_pending(test_run_id) -> list[(ticker, stage)]` for resume support.
2. Decide the on-disk location the same way every other store in this
   project does — via a `VINU_*_DATA_ROOT`-style env var, not a hardcoded
   path, so it's consistent with `require_data_root()`'s no-silent-default
   discipline (see `vinu-infra/config.py`).
3. Write a small test: write a row, crash-simulate (just don't call any
   cleanup), reopen the store, confirm the row is still there with the
   right status.

## Acceptance criteria

- A ticker/stage pair's status survives a process restart with no data
  loss.
- Calling `record()` twice for the same `(test_run_id, ticker, stage)`
  updates the row in place, doesn't create a duplicate.
- `get_pending()` correctly returns only rows that are `pending` or
  missing entirely (i.e. never attempted) for a given `test_run_id`.

## Dependencies

None — this is the foundation task everything else in this folder builds
on.
