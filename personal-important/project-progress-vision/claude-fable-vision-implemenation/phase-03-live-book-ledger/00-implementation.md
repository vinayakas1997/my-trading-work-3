# Phase 3: Live Position / Book Ledger

**Status:** IN PROGRESS
**Started:** 2026-07-26
**Source doc:** ../claude-fable-vision/phase-03-live-book-ledger.md
**Depends on:** —
**Blocks:** Phase 5, Phase 6, Phase 7

## What It Delivers

The `vinu-live` package's own state store — the single source of truth for "what do we currently hold":
- Open positions, size, average entry price, realized/unrealized PnL
- Attached stop/target orders
- Exposure aggregation (per-symbol, per-cluster, portfolio-total)
- Write path (Phase 6 execution engine writes fills/closes here)
- Read path (Phase 4 sizing baseline, Phase 5 circuit breaker, Phase 7 feedback)

Built on the same `SQLiteBackend` foundation proven in `vinu-stock-price` and `vinu-news`.

## Open Questions Resolved

- **Storage backend:** Use `vinu_lib.sqlite.SQLiteBackend` consistent with existing patterns.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu_live/book/__init__.py` | vinu-live | create |
| `vinu_live/book/positions.py` | vinu-live | create |
| `vinu_live/book/exposure.py` | vinu-live | create |
| `vinu_live/book/schema.py` | vinu-live | create |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-position-schema.md` | Position schema and CRUD operations | DONE |
| 2 | `02-task-exposure-aggregation.md` | Exposure aggregation (per-symbol, per-cluster, portfolio) | DONE |

## Dependencies Met

- [x] No dependencies — can start in parallel with Phase 1
