---
name: bug-count-mismatch-in-implementation-agents
status: fixed
severity: documentation-staleness
---

# Bug: `implementation-plan-from-04/AGENTS.md`'s summary table over-counted fixed bugs

## What was wrong

[`implementation-plan-from-04/AGENTS.md`](../../implementation-plan-from-04/AGENTS.md)'s
component summary table stated the `vinu-agent` row as:

> "All 5 pieces implemented (280 tests passing; **+3** real pre-existing
> bugs found and fixed along the way)"

But the detailed, numbered log in that same component's own
[`status.md`](../../implementation-plan-from-04/vinu-agent/status.md)
("Bugs found and fixed while building Piece 2") documents and numbers
exactly **2**:

1. `ground_truth.py`'s `_fetch_open_theses` hit the wrong URL
   (`{research_url}/hypotheses` instead of `/research/hypotheses`) and
   expected the wrong response shape — the "Active Trade Theses"
   ground-truth block had never actually populated in a real run.
2. `trade_plan_tool.py`'s `_write_trade_journal_async` POSTed to the same
   wrong URL — every trade-plan journal write had been silently 404'ing.

No third bug is described or numbered anywhere in that file. The same row
also carried a second, related staleness issue: it quoted `vinu-research`'s
test count as "489 passed project-wide," which — same root cause as
[`stale-test-counts-in-e2e-agents.md`](stale-test-counts-in-e2e-agents.md)
— was the *pre*-work baseline, not the final count (500, per
`vinu-research/status.md`), and didn't credit that row with the
research-digest fix that landed alongside the regime-recompute work.

## Why it mattered

A summary table is the thing most likely to be read on its own, without
opening the detailed status file underneath it — an inflated count here is
exactly the kind of small, checkable inaccuracy that's easy to repeat
verbatim in a later report if nobody goes back to the source.

## What was fixed

In [`implementation-plan-from-04/AGENTS.md`](../../implementation-plan-from-04/AGENTS.md):

- `vinu-agent` row: "+3" → "+2" bugs, matching the two numbered entries in
  `vinu-agent/status.md`.
- `vinu-research` row: "489 passed project-wide" → "500 passed
  project-wide (was 489)," and added the research-digest fix
  (`dispatch()` discarding `run_research()`'s return value) to that row's
  description, since it's real work that row wasn't crediting.

## What was achieved

The summary table's numbers now match their own underlying status files
exactly, so reading the table alone gives the same picture as reading the
detailed log.
