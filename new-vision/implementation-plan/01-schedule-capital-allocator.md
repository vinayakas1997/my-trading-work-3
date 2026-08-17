---
name: schedule-capital-allocator
closes: shortcoming #1 in ../01-vinu-components-shortcomings.md
status: complete — see 01-schedule-capital-allocator-status.md
---

# Task: put `capital_allocator` on a real schedule

## Goal

Add a scheduled worker process that periodically triggers the `capital_allocator` team, the same way
`vinu-agent/entrypoint.sh` already schedules `planner-worker` and `significance-worker`.

## Why

`capital_allocator` is fully wired and correct when invoked — `team.py`'s dispatch branch calls
`apply_capital_allocator_decision`, and `allocation_tool.py` correctly filters PEND artifacts and POSTs
to `/portfolio/evaluate-batch` (a real route in `vinu-portfolio/vinu_portfolio/server/app.py`). But
nothing calls this team on an interval today — it only runs if something else happens to invoke that
team branch. Approved candidates (`ArtifactStatus.PEND`) can sit indefinitely waiting for funding.

## Current state (verified 2026-08-17 — re-check before building)

- `vinu-agent/vinu_agent/server/team.py:71-73` — the dispatch branch: `team_name == "capital_allocator"`
  → `apply_capital_allocator_decision(...)`. This is the entry point the new worker needs to call.
- `vinu-agent/vinu_agent/agent/allocation_tool.py:91` — filters artifacts with `status == PEND`.
- `vinu-agent/vinu_agent/agent/allocation_tool.py:119` — POSTs the batch to
  `/portfolio/evaluate-batch` (`vinu-portfolio/vinu_portfolio/server/app.py:67-68`).
- `vinu-agent/entrypoint.sh` — starts `skill-audit-worker`, `planner-worker`, `significance-worker` as
  background processes before `exec vinu-agent serve`. This is the pattern to copy.
- `vinu-agent/vinu_agent/cli.py` — has `planner_worker_main` (~line 298) as the pattern for a worker
  entry function. No `capital_allocator_worker_main` exists yet — confirmed by grep, not found.
- Grep across the whole `vinu-components` tree at audit time found **no** caller of
  `delegate_to_team("capital_allocator", ...)` on any interval — confirm this is still true before
  building, in case something changed it since.

## Steps

1. Read `vinu-agent/vinu_agent/cli.py`'s `planner_worker_main` in full to understand the existing
   worker-loop pattern (polling interval, error handling, how it calls into the team dispatch layer).
2. Add `capital_allocator_worker_main` to `cli.py` following the same shape: a loop that, on a fixed
   interval, calls whatever internal function `team.py:71-73`'s dispatch branch calls
   (`apply_capital_allocator_decision`, or the `delegate_to_team("capital_allocator", ...)` path if
   that's the real entry point — verify which is correct by reading `team.py` around lines 60-75).
3. Pick and document the cadence. The design doc (`00-full-initial-explanation.md`, "Batching fix" under
   `capital_allocator`) explicitly leaves this cadence undecided — "too slow and approved candidates sit
   idle; too frequent and the batch shrinks back toward first-come-first-served." Start with something
   reasonable (e.g. every 5-15 minutes) and make it configurable via an env var, not hardcoded, so it can
   be tuned without a redeploy.
4. Register the new worker in `entrypoint.sh` alongside the existing six, following the exact same
   backgrounding pattern (`&` + whatever PID/log handling the existing workers use).
5. Make sure the worker's own errors don't crash `entrypoint.sh` — check how `planner-worker` handles
   exceptions in its loop (likely log-and-continue) and match that.

## Acceptance criteria

- A new `capital-allocator-worker` process is visible in `entrypoint.sh` and starts alongside the other
  six workers.
- With a PEND artifact seeded in the test DB, running the worker (or waiting one cadence interval in an
  integration test) results in a call to `apply_capital_allocator_decision` without any external trigger.
- A test exists that starts the worker loop, seeds a PEND artifact, advances time (or uses a short test
  cadence), and asserts the allocator ran — not just that the function is callable in isolation.
- Cadence is configurable via env var with a documented default.

## Dependencies

None — independent of every other task in this plan.
