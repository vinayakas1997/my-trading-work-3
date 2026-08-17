---
name: pre-prod-check-index
status: planning only — nothing in this folder has been implemented or verified yet
purpose: task-by-task skeleton for building the pre-production end-to-end test harness, written so any agent can pick this up and implement it without needing this conversation's history.
---

# Pre-production check — implementation skeleton

## What this is

The system (`vinu-components`) is architecturally complete per
`../04-new-full-explanation.md` — every pipeline stage is built and unit
tested in isolation. What hasn't been verified is the **end-to-end
handoff**: when one real ticker moves through the whole pipeline, does
every stage actually execute, log correctly, and hand off exactly what
the next stage expects? That's a different kind of check than a unit
test, and nothing in the repo does it today.

This folder is the plan for building that check — not the check itself.
No code has been written and no verification has been run against real
code as part of creating these files.

## Why a manifest, not a one-off script

A plain "run everything, see what breaks" script has two failure modes at
this project's scale: if it dies halfway through (crash, killed process,
machine restart), you don't know what already passed without re-reading
logs by hand; and it isn't portable — moving to a new machine means
starting over. The fix decided in conversation: track progress in a
persisted **test manifest**, one row per `(ticker, stage)`, using the
exact same append-only discipline `TickerLedger` already uses for
production events. Resuming is then just "read the manifest, skip
anything already `pass`." Moving machines is just copying the manifest
file plus the DB files it references.

## Task order

| # | Task | Builds |
|---|------|--------|
| 01 | [Test manifest store](01-test-manifest-store.md) | The SQLite store the whole harness depends on |
| 02 | [Stage handoff checklist](02-stage-handoff-checklist.md) | What "pass" means at each of the 7 stages + 2 entry points |
| 03 | [Test harness / CLI](03-test-harness-cli.md) | The runner that drives one ticker through the pipeline and writes to the manifest |
| 04 | [Golden path + edge cases](04-golden-path-and-edge-cases.md) | The actual scenarios to run, not just the happy path |
| 05 | [Go-live gate](05-go-live-gate.md) | The acceptance bar that decides "ready for real capital" vs. "not yet" |

Strict dependency order: 01 before 02 (the checklist needs somewhere to
write results), 02 before 03 (the harness needs to know what to check),
03 before 04 (need the harness before you can run scenarios through it),
04 before 05 (the go-live gate is graded on 04's results).

## Explicitly out of scope here

- **Automated CI integration.** This is a manual/semi-manual
  pre-production pass, not a new CI suite. Could become one later; not
  scoped now.
- **The Jarvis-like watcher-agent / chatbot control layer** discussed in
  conversation — explicitly deferred by the project owner to after this
  pre-prod pass is green, not part of it.
- **Load/performance testing.** This checks correctness of handoffs, not
  throughput or latency under load.
- **Real capital.** Every scenario in task 04 runs against paper/shadow
  execution only, never a live order, regardless of how green the
  manifest looks.
