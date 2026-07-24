# Phased Plan Overview — Storage & Agent Memory

See [00-storage-memory-summary.md](00-storage-memory-summary.md) for the why. This file is the
execution roadmap.

## Status legend

`not started` · `in progress` · `shipped`

## Phases

| # | Phase | Status | Depends on | Detail |
|---|---|---|---|---|
| 1 | Consolidate onto `vinu-lib`'s shared storage primitives | not started | — | [phase-01-adopt-shared-storage-library.md](phase-01-adopt-shared-storage-library.md) |
| 2 | Catalog + watermark pattern for research/simulator storage | not started | Phase 1 | [phase-02-research-simulator-catalog.md](phase-02-research-simulator-catalog.md) |
| 3 | Unified agent-memory layer | not started | Phase 2 | [phase-03-unified-agent-memory-layer.md](phase-03-unified-agent-memory-layer.md) |
| 4 | Context-efficient retrieval for agents/skills/tools | not started | Phase 3 | [phase-04-context-efficient-retrieval.md](phase-04-context-efficient-retrieval.md) |

## Dependency chain

```
Phase 1 (vinu-lib becomes the real shared foundation; stock-price + news migrate)
   │
   └──▶ Phase 2 (same pattern applied to vinu-simulator / vinu-research)
            │
            └──▶ Phase 3 (unified cross-package memory catalog)
                     │
                     └──▶ Phase 4 (agents/skills/tools query memory instead of re-deriving)
```

Phase 1 is foundational and deliberately scoped as a *migration*, not a rewrite — stock-price
and news already have the right design, they just need to sit on one shared, well-tested base
instead of two duplicated ones. Phase 2 is what actually closes the gap identified in
[01-vision-plan](../01-vision-plan/) (Phase 1 and Phase 3 there currently describe hand-rolled
SQLite tables for research/simulation storage — once this folder's Phase 1 ships, those should
be built on `vinu_lib.SQLiteBackend`/`ParquetStore` from the start rather than becoming a third
independent reimplementation).

Phase 3 is the first point where storage stops being purely package-local — it introduces a
cross-package view. Phase 4 is where the investment actually pays off in agent behavior:
without it, Phases 1–3 are "cleaner infrastructure" but nothing consumes it differently yet.

## Relationship to `01-vision-plan`

This folder and [01-vision-plan](../01-vision-plan/) overlap at one seam: `01-vision-plan`'s
Phase 1 (Monte Carlo foundation) and Phase 3 (structured per-iteration storage) both design new
SQLite tables for `vinu-simulator`/`vinu-research`. If this folder's Phase 1 and Phase 2 land
first, `01-vision-plan`'s Phase 1/Phase 3 storage design should be revised to build on the
catalog+watermark base rather than a bespoke `simulation_runs`/`research_runs` key-value table.
If `01-vision-plan`'s Phase 1 lands first (it's the one currently approved to start), its
storage design should be treated as provisional and revisited once this folder's pattern is
ready, rather than becoming permanent. **Recommendation: flag this dependency explicitly before
`01-vision-plan` Phase 1 implementation begins**, since redoing storage twice is exactly the
kind of duplicated effort this folder exists to prevent.

## Files touched, by service

- **vinu-lib** (`vinu-components/vinu-lib/`): Phase 1.
  - `sqlite.py` (`SQLiteBackend`), `parquet.py` (`ParquetStore`), `db.py` (migration helpers)
- **vinu-stock-price** (`vinu-components/vinu-stock-price/`): Phase 1 (migration only, behavior
  unchanged).
  - `vinu_stock/catalog/store.py`, `vinu_stock/storage/parquet.py`
- **vinu-news** (`vinu-components/vinu-news/`): Phase 1 (migration only, behavior unchanged).
  - `vinu_news/backfill/store.py`, `vinu_news/analysis/storage/`
- **vinu-simulator / vinu-research**: Phase 2 (new work, coordinated with `01-vision-plan`).
- **New cross-package memory module** (likely `vinu-lib` or a new small package): Phase 3.
- **vinu-agent** (skills, tools, agent loop context-building): Phase 4.

## Approval status

Nothing in this folder is approved to start. This is documented so the storage-design decision
is visible before `01-vision-plan` Phase 1 implementation locks in a design that would need to
be redone.
