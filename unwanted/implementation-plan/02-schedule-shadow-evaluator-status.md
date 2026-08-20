---
task: 02-schedule-shadow-evaluator.md
status: complete (verified already-built)
---

# Status: task 02 — put `ShadowEvaluator.evaluate_all()` on a real schedule

## Files touched

None — this task was already fully implemented and tested before this plan
was executed. Audit findings confirmed it (the two audits the task doc said
disagreed; the task doc's own "verify directly" instruction resolved it:
the `shadow-worker` process exists at `entrypoint.sh:23` and *does* call
`evaluate_all()` on its own timer).

## What I did

- Read `vinu-live/entrypoint.sh` in full: line 23 starts `vinu-live shadow-worker &`
  as a background loop before `exec vinu-live serve` — alongside
  `vinu-live-worker --interval 3600 &` (line 14), `trade-plan-worker` (line 15),
  `feedback-worker` (line 16). The comment block (lines 17-22) documents it as
  the Phase-9 scheduler-wiring fix for the missing `ShadowEvaluator` caller.
- Read `shadow_worker_main` in `vinu-live/vinu_live/cli.py:117-166`: it constructs
  `ShadowEvaluator`, loops `while True: await evaluator.evaluate_all(); sleep(interval)`,
  logs per-cycle structured results (`vinu_ctx`), and on failure does
  `log.exception(...)` then `raise` — the exact error-handling shape of
  `trade-plan-worker`/`feedback-worker`. KeyboardInterrupt → clean stop.
- Confirmed the cadence is env-configurable, not hardcoded:
  `config.shadow_worker_interval_sec` default 3600s sourced from
  `VINU_LIVE_SHADOW_INTERVAL` (`vinu-live/vinu_live/config.py:80-83`), with
  `--interval` overriding.
- Confirmed the CLI subparser `shadow-worker` is registered
  (`vinu-live/vinu_live/cli.py:315`).
- Confirmed the acceptance-criterion tests already exist and pass:
  - `test_cli.py:46` `test_calls_evaluate_all_and_stops_on_keyboard_interrupt` —
    runs the real worker loop one cadence tick (mock `evaluate_all`), asserts it
    was called, then KeyboardInterrupt stops the loop.
  - `test_shadow_evaluator_real_endpoint.py:70` `test_evaluate_all_promotes_via_the_real_endpoint_end_to_end`
    — seeds a BENCHING artifact whose paper Sharpe is within tolerance, runs
    unmodified `evaluate_all()` against the real (in-process) agent endpoint,
    asserts promotion to ACTIVE.
  - `test_shadow_evaluator.py` — tolerance-based promotion / within-tolerance
    promotion / below-tolerance withholding (no promote call).

## What is achieved

- `ShadowEvaluator.evaluate_all()` is invoked automatically on a fixed, env-tunable
  cadence — no manual CLI invocation or external HTTP call needed. The "paper-trading
  phase becomes an automated gate" behavior the evaluator was built for is now live.

## Alignment with plan-justification

- The task doc's step 1 ("read entrypoint.sh and determine definitively whether a
  shadow-worker process already exists") resolved in favor of "exists and already
  calls evaluate_all on its own timer" — so step 2's branch applied, and the work
  was already done. Nothing to add; closing as verified-complete with the audit
  trail above in case the docs need reconciling.

## Testing

- `python3 -m pytest vinu-live/tests/test_shadow_evaluator.py vinu-live/tests/test_cli.py -q` → 12 passed.
- No code changed in this task.