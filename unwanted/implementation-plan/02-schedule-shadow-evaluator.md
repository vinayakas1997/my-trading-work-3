---
name: schedule-shadow-evaluator
closes: shortcoming #2 in ../01-vinu-components-shortcomings.md
status: complete — see 02-schedule-shadow-evaluator-status.md
---

# Task: put `ShadowEvaluator.evaluate_all()` on a real schedule

## Goal

Add a scheduled worker (or extend an existing one) in `vinu-live` that calls
`ShadowEvaluator.evaluate_all()` on a fixed interval, instead of only via manual CLI or an
externally-triggered HTTP route.

## Why

`ShadowEvaluator` (in `vinu-live/vinu_live/shadow_evaluator.py`) already does real, correct work — it
compares a BENCHING artifact's paper-trading Sharpe against its backtest Sharpe and auto-promotes to
ACTIVE within tolerance. Its own docstring calls this "the paper-trading phase becomes an automated
gate." But nothing calls it automatically. Shadow-vs-backtest comparisons currently only happen if
something outside the codebase manually triggers them.

## Current state (verified 2026-08-17 — re-check before building)

- `vinu-live/vinu_live/shadow_evaluator.py` — `ShadowEvaluator.evaluate_all()` is the real entry point.
  The earlier-documented "broken endpoint" bug (calling a 404ing `/agent/broker/performance/{artifact_id}`
  route) is already fixed — confirm `routes_broker.py:114-132` in `vinu-agent` still has both
  `GET`/`POST /broker/performance/{artifact_id}` before assuming this.
- `vinu-live/vinu_live/cli.py` — has a manual CLI path to call `evaluate_all()`.
- `vinu-live/vinu_live/server/app.py:59-64` — has an HTTP route that also calls `evaluate_all()`, but
  only when hit.
- `vinu-live/entrypoint.sh:14-16,23` — starts `trade-plan-worker`, `feedback-worker`, and (per one audit
  pass) a `shadow-worker` reference at line 23. **Verify directly** whether a `shadow-worker` process
  already exists here and simply doesn't call `evaluate_all()` on its own timer (in which case this task
  is "wire the existing worker to actually call evaluate_all periodically") versus no such process
  existing at all (in which case this task is "add the worker from scratch"). The two audits that fed
  this plan disagreed slightly on this point — resolve it by reading `entrypoint.sh` directly first.

## Steps

1. Read `vinu-live/entrypoint.sh` in full and determine definitively whether a `shadow-worker` process
   already exists and what it currently does.
2. If it exists but doesn't call `evaluate_all()` on an interval: locate its current loop body and add
   the call, with a configurable interval (env var, not hardcoded).
3. If it doesn't exist: create it following the same pattern as `trade-plan-worker`/`feedback-worker` in
   the same file — a background loop process calling `ShadowEvaluator.evaluate_all()` on a fixed
   interval, registered in `entrypoint.sh` the same way.
4. Decide and document the cadence — shadow comparisons don't need to run as often as the live trade-plan
   loop, but shouldn't be so infrequent that a BENCHING artifact sits unpromoted for a long stretch after
   clearing tolerance. Look at what interval `trade-plan-worker`/`feedback-worker` already use as a
   starting reference point.
5. Confirm error handling matches the existing workers (log-and-continue, not crash-the-process).

## Acceptance criteria

- `ShadowEvaluator.evaluate_all()` is called automatically on a fixed interval without any manual CLI
  invocation or external HTTP call.
- A test seeds a BENCHING artifact whose paper-trading Sharpe is within auto-promotion tolerance of its
  backtest Sharpe, runs the worker (or one cadence tick in a test harness), and asserts the artifact was
  promoted to ACTIVE — exercising the real scheduled path, not just calling `evaluate_all()` directly in
  a unit test.
- Cadence is configurable via env var with a documented default.

## Dependencies

None.
