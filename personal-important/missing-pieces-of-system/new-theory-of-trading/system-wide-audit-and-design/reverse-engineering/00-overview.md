# Reverse-engineering the live decision loop

**This folder exists to work backward from one specific end goal**:
before `vinu-live` acts on a trade, it should (1) check that the
strategy's precondition is actually true right now, and (2) ask the 29th
angle's recorded evidence (`get_signal_evidence`/`get_move_evidence`)
what's historically happened the last N times this exact condition
fired — and decide based on both. That end goal is confirmed already
written into the design in `../../00-explanation.md` (Layer 5, "Risk
management from experience, live use") and
`../../how-to-use-29th-angle/01-track1-how-it-works-today.md` (the "LIVE
detector... does not exist" line), and cross-referenced against every
relevant gap already found in `../` (the parent audit series).

**Method**: instead of reading the audit top-to-bottom, start from the
end goal and ask "what does vinu-live actually need to do this," then
trace each need back to whether it already exists, is a known gap, or is
new. This is a different pass than the parent folder's `02-open-
questions-strategy-and-simulation.md`, which found gaps by auditing each
component in isolation — this folder finds gaps by trying to assemble
one specific end-to-end capability and seeing what's missing along the
way.

## Files in this folder

- `00-overview.md` — this file.
- `01-live-decision-loop-open-points.md` — the 9 points identified so
  far: what needs to exist, per-point, for a ticker's strategy to go
  from "candle closed" to "a safe, evidence-informed decision actually
  reaches execution." Each point says what's already real, what's a
  known gap from the parent audit, and what's newly surfaced here.
- `02-implementation-status.md` — a single, kept-current place to check
  which of the 9 points are still just design vs. actually built.
  Updated every time a point gets a real schema/API design or real code,
  not written once and left stale.
- `03-poller-and-state-schema.md` — points 2 (candle-close poller) and 4
  (stage/state tracker) designed in schema/loop detail: table shapes,
  the poll loop, the state machine and its transition rules. Designed
  together since the poller drives the state tracker directly. The first
  two points chosen to design in detail, since everything else in the
  list depends on this foundation existing first.
- `04-live-detector-schema.md` — point 3 (the live indicator "detector"),
  grounded against real `vinu-tools`/`vinu-stock-price` code: confirms
  no new indicator math is needed, specifies the live-fetch contract,
  and flags the one real risk (a 5th instance of the duplicated-
  computation pattern if live and backfill diverge).
- `05-deciding-agent-and-precondition-tracking.md` — points 5 (the
  querying/deciding agent) and 6 (precondition `defined`/`tested`
  tracking) designed together, modeled directly on `vinu-agent`'s real
  `BaseTool`/`AGENT.md` pattern (`theory_reviewer` as the precedent):
  the new `get_live_decision_context` tool and `live_decision_agent`,
  and exactly what write-back flips the `tested` flag.
- `06-execution-handoff-and-architecture.md` — points 7 (decision ->
  execution handoff, tying directly into item #24's `check_limits`/
  same-symbol-netting gaps — **both now built**, see that doc and
  `../02-open-questions-strategy-and-simulation.md` item #24's own
  2026-09-26 UPDATE) and 8 (where all of this architecturally lives —
  `vinu-live` for the poller/detector/tracker, `vinu-agent` for the
  deciding agent — **built as designed**), grounded against the real
  `breaker/engine.py::check_limits` signature and confirmed directory
  structure.
- `07-bucket-table-deferred.md` — point 9 (Layer 4's probabilistic
  bucket table), deliberately kept undesigned in detail, consistent with
  `01-planning.md`'s own stated reason: no real accumulated data exists
  yet to validate a bucketing scheme against. Explains what unblocks it
  and why points 5/6 don't need to wait for it.

## Status

**Updated 2026-09-26 — see `02-implementation-status.md` for the single
kept-current source of truth.** All 9 points are designed (point 9
deliberately deferred, real reason given). 8 of 9 points are built and
tested for real, end to end: a candle close is detected, a stage/state
tracker evaluates must/confirmation conditions against a live indicator
snapshot, a fresh `ready_to_execute` triggers `live_decision_agent`
(reads real historical evidence, its own real prior verdicts, and the
strategy's precondition claim before deciding), every verdict is durably
recorded and queryable, and an EXECUTE decision — if the strategy is
sized — flows into a real order through `LiveScheduler`, gated by the
same risk-limit check and same-symbol netting this work also added
(closing item #24's two CRITICAL gaps in the parent audit, see its
2026-09-26 UPDATE). `live-decision-worker` is wired into the real
deployment (`entrypoint.sh`, `docker-compose.yml`), not just tested in
isolation. Point 9 (the probabilistic bucket table) remains deliberately
undesigned — no real accumulated data exists yet to validate a bucketing
scheme against, see `07-bucket-table-deferred.md`.

**What's still genuinely open, not silently assumed away**: point 6's
`precondition.tested` write-back path/storage; how a position a live
EXECUTE opened ever exits (no exit mechanism exists for it yet —
reconciliation only reports drift on it, never acts); item #24 finding
#3 (reconciliation drift never alerted on this path); and everything
else in the parent audit this folder never touched (items #1-23, #25,
most of #26 — see `../00-overview.md`'s own status section).
