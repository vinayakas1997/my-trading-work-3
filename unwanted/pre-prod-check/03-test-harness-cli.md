---
name: test-harness-cli
status: planning only — not yet implemented
---

# Task: build the harness that drives a ticker through the pipeline and checks it off

## Goal

A CLI (or small script) that takes a `test_run_id` and a ticker, walks it
through the real pipeline stage by stage, evaluates each stage against
task 02's checklist, and writes the result to task 01's manifest —
resuming automatically from the first non-`pass` stage if run again for
the same `test_run_id`/ticker.

## Why

Manual checking (reading logs by hand after each stage) doesn't scale
past one or two tickers and leaves no durable record. This turns the
checklist from task 02 into something repeatable and resumable, which
matters because — per the project owner — "this is the bigger app,
suppose somewhere it stopped in the middle" is an expected occurrence,
not an edge case to design around later.

## Steps

1. `scripts/pre-prod-run.sh <test_run_id> <ticker> [--resume]` (or
   equivalent Python entry point) as the operator-facing command.
2. On start, call task 01's `get_pending(test_run_id)` — if `--resume`
   and rows already exist, skip straight to the first `pending` stage
   instead of re-running from `watchlist_gate`.
3. For each stage in task 02's order:
   a. Trigger the real stage (however it's actually invoked in
      production — a worker function call, an API request, whatever the
      real entry point is; do not build a second, parallel invocation
      path just for testing).
   b. Evaluate the stage's checklist condition.
   c. Write the result via task 01's `record()` — `pass` with
      `evidence_ref` pointing at the real row/artifact it produced, or
      `fail` with `notes` describing exactly what didn't hold.
   d. On `fail`, stop — don't cascade into stages that depend on this
      one's output; a downstream `fail` on top of an upstream `fail`
      just adds noise, not information.
4. Print a summary at the end: stages passed / failed / still pending for
   this ticker, plus the manifest rows so the operator (or a resuming
   agent) can act on the specific failure.

## What "resumable on a new machine" requires

- The manifest DB file (task 01) and the real stores it references
  (`TickerSummaryStore`, `SqliteStrategyStore`, `HypothesisRegistry`,
  `TickerLedger`, etc.) all need to move together — copying only the
  manifest without the underlying data roots it points to makes
  `evidence_ref` unresolvable.
- No in-memory state should matter across a restart — every fact the
  harness needs to decide where to resume from must already be in the
  manifest, not held in a running process's memory.

## Acceptance criteria

- Running the harness against a ticker end to end (nothing failing)
  produces a manifest with every stage from task 02 marked `pass`.
- Killing the harness mid-run (e.g. `kill -9` between two stages) and
  re-running with `--resume` picks up exactly at the next unattempted
  stage — no re-execution of already-`pass` stages, no skipped stages.
- A deliberately-failing scenario (see task 04) correctly stops at the
  failing stage and records `notes` specific enough that someone reading
  only the manifest (not the logs) can tell what broke.

## Dependencies

Depends on tasks 01 and 02.
