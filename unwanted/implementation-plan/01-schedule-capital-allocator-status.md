---
task: 01-schedule-capital-allocator.md
status: complete
---

# Status: task 01 — put `capital_allocator` on a real schedule

## Files touched

- `vinu-agent/vinu_agent/config.py` — added `capital_allocator_worker_interval_sec` (default 900s) and
  `capital_allocator_budget` (default 100000.0) to `AgentConfig`, wired to env vars
  `VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL` and `VINU_AGENT_CAPITAL_ALLOCATOR_BUDGET` in `load_config`.
- `vinu-agent/vinu_agent/agent/scheduler_workers.py` — added `run_capital_allocator_cycle(service, *, budget, cycle)`.
- `vinu-agent/vinu_agent/cli.py` — added `capital_allocator_worker_main(args)` + `capital-allocator-worker`
  subparser + dispatch branch; imported `run_capital_allocator_cycle`.
- `vinu-agent/entrypoint.sh` — registered `vinu-agent capital-allocator-worker &` alongside the other workers.
- `vinu-agent/tests/test_capital_allocator_worker.py` — new test file (5 tests).

## What I did

- Verified the dispatch path before building (task doc's `server/team.py:71-73` path was wrong): the real
  runner is `vinu_agent/agent/team.py`'s `TeamManager`; the canonical worker→team invocation is
  `run_team_for_ticker(service, team_name, task, *, session_id)` in `agent/scheduler_workers.py`; the hook
  `apply_capital_allocator_decision` lives in `agent/capital_allocator_hook.py` and is invoked by the team
  itself after its final decision. The worker therefore triggers the team and the team applies the hook —
  same shape planner-worker already uses for its research hand-off.
- Implemented `run_capital_allocator_cycle`: reads every PEND artifact in one shot via
  `SqliteStrategyStore.list_artifacts_by_statuses([ArtifactStatus.PEND])`; skips the LLM run entirely when
  the batch is empty (`status: skipped`); otherwise builds the task string (all PEND ids + the configured
  budget, matching `teams/capital_allocator/manager_prompt.md`'s "whole PEND batch at once, plus the current
  risk budget") and calls `run_team_for_ticker(service, "capital_allocator", task, session_id="capital-allocator-<cycle>")`.
- Implemented `capital_allocator_worker_main` in cli.py with the exact `while True: cycle(); sleep()` +
  `log.exception`-then-`raise` + `KeyboardInterrupt` shape of the existing workers; structured logging via
  `vinu_ctx` (per task 10). Cadence resolved via `resolve_worker_interval(args, config, ...)`.
- Registered the worker in `entrypoint.sh` before `exec vinu-agent serve`, same `&` backgrounding pattern.
- Wrote 5 tests covering: empty-batch skip (no team call), batch→team handoff (team name, all PEND ids in
  task, budget formatted, session id), PEND-only status query, and both config defaults.

## What is achieved

- `capital-allocator` now has a real scheduled caller: every 15 min (default) the whole PEND batch is handed
  to the team for funding, so approved candidates no longer sit PEND indefinitely.
- Cadence and budget are env-configurable, not hardcoded.
- No-PEND cycles cost zero LLM calls; failures are crash-loud with a structured record.

## Alignment with plan-justification

- Cadence 900s sits inside the 5-15 min band the design doc explicitly leaves open; first-pass unvalidated
  default, same category as every other un-pinned threshold in this build. Budget is a config placeholder
  (pending a real funding-capital source like broker buying power) — flagged in the config comment.
- The worker triggers the team rather than calling `apply_capital_allocator_decision` directly, because the
  hook is the team's post-decision action; this matches the acceptance criterion ("call to
  `apply_capital_allocator_decision` ... without any external trigger") — the team applies the hook itself
  when run.

## Testing

- `python3 -m pytest vinu-agent/tests/test_capital_allocator_worker.py -q` → 5 passed.
- `python3 -m pytest vinu-agent/tests -q` → 802 passed (797 prior + 5 new).
- `python3 -m py_compile` clean on all edited modules.