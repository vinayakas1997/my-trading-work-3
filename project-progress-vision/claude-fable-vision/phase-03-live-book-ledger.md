# Phase 3 — Live Position / Book Ledger

Status: **not started** · Depends on: — · Blocks: Phase 5, Phase 6, Phase 7

## What it is

The `vinu-live` package's own state store — the single source of truth for "what do we
currently hold": open positions, size, average entry price, realized/unrealized PnL, and any
attached stop or target. Every environment in the architecture owns a catalog of *history*
(`vinu-stock-price`'s `symbol_catalog`, `vinu-initial-analysis`'s angle runs, `vinu-research`'s
`research_runs`); none owns a catalog of *now*. This is that catalog, scoped specifically to
`vinu-live` since Initial-Analysis and Research-Simulations have no need to track live positions
— only production execution does.

## Impact

**Before this phase:** Nothing in the system can answer "what are we exposed to right now"
without querying a broker directly. Phase 5's circuit breaker has nothing to check limits
against; Phase 4's trade-plan authoring has no live baseline to size relative to.

**After this phase:** A single query returns current exposure per symbol, per shock-cluster
group (once Phase 2 exists), and in total.

**What still won't work after this phase alone:** The book is a passive ledger until Phase 6's
execution engine writes fills into it and Phase 5's breaker reads from it as part of a live
check.

## Where changes occur

- New package `vinu-live/` — a `book` module/schema for `positions` (open/closed, size, entry,
  stop/target) and an `exposure` aggregation (per-symbol, per-cluster, portfolio-total), built
  on the same `SQLiteBackend`/`ParquetStore` foundation already proven in `vinu-stock-price` and
  `vinu-news`.
- Write path: only Phase 6's execution engine should write fills/closes here — no other
  component mutates position state directly.
- Read path: Phase 4 (trade-plan sizing baseline), Phase 5 (circuit breaker), Phase 7 (feedback
  attribution) all read from this ledger.

## Why we need this

Sizing, circuit-breaker checks, and cluster-exposure checks are all *relative* decisions — "how
much more can we take on" only means something next to "how much do we already have." Without a
single ledger, every check would re-derive current exposure from a broker API independently,
which is slow, fragile, and can give different components a different answer if queried at
different times. One ledger, written by exactly one component, read by everything else, removes
that class of bug.

## How to test it

- Unit tests: opening, adding to, reducing, and closing a position produce correct size,
  average-entry, and realized/unrealized PnL.
- Concurrency test: two near-simultaneous fills for the same symbol resolve to a correct
  aggregate position, not a race/overwrite — mirrors the dedup-on-write discipline already
  proven in `vinu-stock-price`'s `(symbol, provider, bar_ts)` keying.
- Aggregation test: per-symbol, per-cluster, and portfolio-total exposure sums match a
  hand-computed total across a seeded set of synthetic positions.
