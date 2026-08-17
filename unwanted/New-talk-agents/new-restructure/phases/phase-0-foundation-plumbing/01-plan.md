---
name: phase-0-plan
status: proposed-not-built
purpose: deep-dive plan for Phase 0 of the 9-phase build order -- foundation plumbing that every later phase writes into or reads from. No new agent behavior, no LLM changes.
---

# Phase 0 -- Foundation plumbing

## What this phase builds

Three pieces, none of them agents, none of them touch an LLM:

1. **`TickerLedger`** -- new SQLite store, one row per ticker-relevant
   event across the whole pipeline.
2. **RunLog-driven trigger** for the Summary Agent -- what causes it to
   refresh at all.
3. **Change-gate (`GATE`)** ahead of the Planner -- the cheap check that
   stops the Planner running an LLM pass on tickers where nothing changed.

Build order within the phase: `TickerLedger` first (nothing else in this
phase depends on it, but everything in *later* phases writes into it, so
get the schema right once here) -> RunLog trigger second -> change-gate
third (it directly consumes what the RunLog trigger produces).

## 1. `TickerLedger`

**Where it lives:** `vinu_agent/storage/ticker_ledger.py`, new file, sibling
to `ticker_summaries.py`/`team_runs.py`/`llm_calls.py`.

**Base class:** `class TickerLedgerStore(SQLiteBackend):`, importing
`from vinu_infra.sqlite import SQLiteBackend` -- confirmed this is the real,
consistent base every existing storage module in `vinu_agent/storage/`
already uses (`team_runs.py:181`, `llm_calls.py:136`, `ticker_summaries.py:64`
all subclass it). Do not invent a second storage pattern.

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS ticker_ledger (
    ledger_id   TEXT PRIMARY KEY,
    ticker      TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    stage       TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    text        TEXT NOT NULL,
    ref_id      TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_ticker_ledger_ticker ON ticker_ledger(ticker);
CREATE INDEX IF NOT EXISTS idx_ticker_ledger_stage ON ticker_ledger(stage);
```

- `ledger_id`: `uuid.uuid4().hex[:12]` -- the exact ID convention already
  used project-wide (`team_runs.py`, `session/models.py`, `swarm/models.py`,
  `llm_calls.py`, `facts/registry.py` all generate IDs this way; no
  exceptions found anywhere in `vinu_agent`). Don't use an autoincrement
  int or a different UUID length -- staying consistent means any tool
  that already knows how to log/display an id (e.g. audit tooling) works
  here without a special case.
- `ref_id`: points at the record in whichever specialized store actually
  owns the data -- `artifact_id` (`SqliteStrategyStore`), `run_id`
  (`team_runs`), or a hypothesis id (`HypothesisRegistry`). `TickerLedger`
  is a narrative index, never a duplicate copy of the real data.
- `stage`/`event_type` stay plain `TEXT`, not an enum or foreign key --
  new stages get a new string value, no migration required. (A companion
  taxonomy file, same pattern as `skills/strategy-tags/tags.yaml`, is an
  open question -- see `02-guard-rail.md`.)
- `source`: which entry point produced this row -- `"watchlist"` or
  `"human"` (matches the tag `HypothesisRegistry` already uses for
  Thesis Intake / human-override rows, so a `TickerLedger` row and its
  `ref_id`-linked `HypothesisRegistry` row agree on provenance).

**Write points in this phase:** none yet -- Phase 0 only creates the store
and its write API (`add_event(ticker, stage, event_type, text, ref_id="",
source="watchlist")`). The 8 real call sites (Thesis Intake, Summary Agent,
Planner, Researcher/Executor, `risk_gatekeeper`, `capital_allocator`,
Monitor, human override) get wired in as each of *those* phases lands --
Phase 0 just makes sure the table and the write method exist and are
tested standalone before anything depends on them.

## 2. RunLog-driven trigger for the Summary Agent

**What exists already, confirmed by reading the code:**
`vinu-initial-analysis/vinu_initial_analysis/storage/meta.py`'s `RunLog`
is real, already built, already the project's "latest" resolution
mechanism -- nothing new to build here except the watcher.

**What Phase 0 adds:** a small poll/watch step that asks, per ticker,
"has `RunLog` produced a `run_id` newer than the one `TickerSummaryStore`
last recorded in its `source_run_id` column?" If yes, the Summary Agent
re-runs for that ticker and writes the new `source_run_id` back. If no,
nothing happens -- and there is nothing new for the change-gate below to
find, either.

**Where it plugs in:** wherever the Planner's cycle currently begins
iterating the watchlist -- this check runs once per ticker, before the
Summary Agent is even considered, not inside the Summary Agent itself.

## 3. Change-gate (`GATE`) ahead of the Planner

**What it checks**, cheap and deterministic, no LLM call either way:
has `TickerSummaryStore`'s `source_run_id` **or** this ticker's artifact
status (via `SqliteStrategyStore.list_artifacts_for_symbol`, real,
already used by `broker/order_guard.py`) changed since the Planner last
looked at this ticker?

- **"no"** -> advance to the next ticker in the watchlist. Not a retry of
  this one -- this edge was previously an unlabeled loop back to the
  watchlist node and had to be made explicit (see `mermaid-explanation.md`,
  Loop-termination pass) specifically so it doesn't read as an infinite
  spin.
- **"yes"** -> Summary Agent runs (if the RunLog trigger above says its
  data is stale) or the Planner runs directly on the existing summary (if
  only the artifact status changed, not the underlying analysis).

**Where "last looked at this ticker" is stored:** this needs its own small
piece of state -- a per-ticker `last_checked_run_id` / `last_checked_status`
pair. Cheapest correct place for it: a new column pair on
`TickerSummaryStore` itself (it's already the one-row-per-ticker store),
not a new table -- avoids a second store for what's really one fact about
the existing row. Confirm this against `TickerSummaryStore`'s real schema
before implementing; it may already have room via `source_run_id`.

## Critical points carried into this phase from the wider design

- This phase is why `TickerLedger`'s schema has to be gotten right *now*,
  even though nothing writes to it yet -- every later phase's write points
  are already enumerated in `mermaid-explanation.md`'s "Where the ticker's
  full story actually lives" section. Changing the schema after Phase 1+
  starts writing to it means a migration; getting it right here avoids
  that.
- The RunLog trigger and the change-gate are two different checks that
  happen to run back-to-back -- don't collapse them into one function.
  The RunLog trigger answers "is the underlying analysis stale," the
  change-gate answers "has anything relevant to the Planner changed."
  A ticker can trip the second without the first (e.g. an artifact just
  finished BENCHING) or the first without immediately tripping the second
  in the same pass.
