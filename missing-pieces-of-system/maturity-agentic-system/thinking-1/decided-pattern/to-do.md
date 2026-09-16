# To-do: what's still missing before this can be built

## Context

`decided-pattern.md` (same folder) is the settled narrative — the 9
steps, where Graphiti fits, the diagram, the worked example. It's
complete as an *explanation*. It is **not** a build spec. This doc is
the concrete list of what still has to be decided and written, in
numbers and schemas, before any of the 6 analysts, Layer 0, or the
brain can actually be coded. Nothing in this list has been done yet.

Per `agents-implementation-plan.md`'s own build order, item 1 (Layer 0's
schema) and item 2 (starting with just the Decision-Process analyst,
owns analysis D) are the actual next concrete steps — not all 8 items
need to be finished before anything can start; #1 and a single
scoped-out analysis from #2 unblock the first real build.

---

## 1. No actual table schema (DDL)

`reflection_findings_history` and `reflection_beliefs` are only
described in prose so far. Needed: a real `CREATE TABLE` for each,
following the exact same pattern every other store in this codebase
already uses (`vinu_infra.sqlite.SQLiteBackend` — `SCHEMA` +
`SCHEMA_VERSION` + `MIGRATIONS`, thread-local connections, WAL mode).

At minimum, `reflection_findings_history` needs: `finding_id`,
`analyst_name`, `cluster`, `scope_type`, `scope_key`, `computed_at`,
`signal_json`, `evidence_count`, `severity`, `narrative`. `reflection_beliefs`
needs the same fields but keyed for overwrite (`PRIMARY KEY (analyst_name,
scope_type, scope_key)` or similar), holding only the current state per
topic.

**Why this is first**: nothing else can be written or tested without
this existing.

## 2. No per-analysis query-level scoping for the 25 (A–Y)

The single largest remaining gap. Every analysis in
`data-driven-analysis-opportunities.md` is still one paragraph — "join
X × Y × Z" — not a real, runnable SQL query with real column names.
Needed, per analysis: the exact tables/columns involved (already mostly
named in each analysis's "Join" line), the exact join keys, and what
the query actually returns.

**Recommended order**: don't try to scope all 25 at once. Per
`agents-implementation-plan.md`, start with **D** (Decision-Process) —
`llm_calls.db` and `telemetry.db` are zero-reader stores today, so this
is a pure read + join with no new writer needed anywhere, the fastest
possible proof the whole pipeline works end to end. Scope D fully
(query, thresholds, output shape) before touching the other 24.

## 3. No concrete significance thresholds

"Is this new, changed, or degraded" is conceptually right but
unquantified everywhere. Needed, per analysis: an actual number. E.g.
"a Brier-score delta of ≥0.05 over the last N calibration entries counts
as significant" (for A), "correlation must climb by ≥0.15 over 3+
consecutive weekly checks" (for E). Without these, `evidence_count` and
the gate itself can't be coded — this is the threshold that decides
whether anything gets written to Layer 0 or Hindsight at all.

**Depends on #2** — can't set a threshold for a query that doesn't
exist yet. Scope both together, per analysis, not as separate passes.

## 4. No analyst plug-in interface

`six-agents-critique-and-hindsight-memory-resolution.md` names the
shape (`(data_root_paths) -> list[Finding]`) but it's never been
written as an actual Python interface/protocol to build every analyst
against. Needed: a real `Finding` dataclass (mirroring the
`reflection_findings_history` schema from #1) and a real function
signature every one of the 6 analyst modules implements, so
`reflection_worker_main`'s registry loop can call them uniformly.

## 5. No decision on where the brain/analysts physically run

Discussed in conversation, never written down as a locked decision.
The implied answer (matching `skill-audit-worker`'s exact shape —
`resolve_worker_interval(...)` → `while True: cycle(); sleep()` in
`vinu-agent/vinu_agent/cli.py`) is that this lives as one more worker
process inside **vinu-agent**, alongside every other worker of this
shape. Needs to be stated as an actual decision (or overridden) before
`reflection_worker_main` gets written into a specific file, not left as
an inference from "we're copying vinu-agent's pattern."

## 6. No Hindsight bank lifecycle details

Two concrete open questions: (a) who creates a ticker's Hindsight bank
the first time that ticker enters the watchlist — does
`bootstrap_new_tickers` (vinu-agent, already exists) also need to
provision a bank, or does the first `retain()` call implicitly create
one? (b) the exact tag *key* schema — `other-findings-methods.md` and
`six-agents-critique...md` give examples (`date`, `regime`,
`source_analyst`) but never a locked, final list of tag keys every
`retain()` call must populate consistently, which matters because
`observation_scopes` (shared vs. per-tag-combination) depends on
exactly which tags are present.

## 7. No failure-isolation restated as a concrete requirement

`six-agents-critique-and-hindsight-memory-resolution.md` requires each
analyst to fail independently inside the shared worker loop (its own
try/except, logged, skipped — same discipline `AuditLogger.log()`
already uses) so one analyst's bug can't take down the other five's
cycle. This needs to be carried into whatever file actually implements
`reflection_worker_main` as an explicit requirement, not just a note in
a design doc — easy to accidentally skip when writing the real loop.

## 8. No schema for the brain's own self-trust tracking

Step 9 of `decided-pattern.md` describes logging the brain's own
synthesis predictions against later observed outcomes, gating how much
weight its narrative carries by its own accumulated sample size — but
no table exists for this yet. Needed: a store (same `SQLiteBackend`
pattern again) holding at minimum `synthesis_id, computed_at,
prediction_json, observed_outcome_json NULL, resolved_at NULL` — written
when the brain synthesizes, updated later when the predicted outcome is
actually known. This is lower priority than 1–4 since it only matters
once the brain itself exists (step 8), which is last in the build
order anyway.

---

## What actually unblocks building, today

Only **#1** (Layer 0 schema) and a fully-scoped **#2/#3 for analysis D
alone** (per `agents-implementation-plan.md`'s recommended starting
point) are needed to write and test the first real piece of this
system end to end. #4–8 matter, but not before that first slice exists
and proves the pattern works.
