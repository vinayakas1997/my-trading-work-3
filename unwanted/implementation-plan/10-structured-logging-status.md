---
name: 10-structured-logging-status
task: 10-structured-logging
status: complete
date: 2026-08-17
---

# Status: 10-structured-logging

## Re-verification note (audit was partially stale)

The task file claimed "zero structured logging/error tracking found anywhere in
`vinu-components`." Direct code read found this is **not** true:

- `vinu-infra/debug.py` already ships `setup_logging(service)`, and every service
  CLI already calls it (`vinu-agent/vinu_agent/cli.py:386`, `vinu-live/vinu_live/cli.py:255`,
  and all nine other services). The audit's "no logging anywhere" claim is stale.
- What was genuinely missing: worker loops emit events via bare `print()`
  (invisible to the logging subsystem, so never captured by the shared file sink),
  records are human-readable text only (not structured/queryable JSON), and only
  one worker (`planner_worker_main`) logged exceptions.

The task was therefore implemented as *extend the existing substrate*, not *build
from scratch*.

## Files touched

- `vinu-infra/debug.py` — added `JsonFormatter` (one JSON object per line: ts UTC,
  service, level, logger, message, `vinu_ctx` extras, exc_type + traceback when an
  exception is attached), `_ServiceFilter` (stamps the service name onto every
  record), and extended `setup_logging(service, *, verbose=False, structured_path=None)`
  to append a structured JSONL sink when `structured_path` or `VINU_STRUCTURED_LOG`
  is set.
- `vinu-infra/tests/test_logging.py` — new: 4 tests covering the formatter, missing-ctx
  handling, traceback inclusion, and end-to-end `setup_logging` → JSONL file.
- `vinu-agent/vinu_agent/cli.py` — `skill_audit_worker_main`, `planner_worker_main`,
  `significance_worker_main` converted from `print()` to `logging` with structured
  `vinu_ctx` (worker, ticker, counts); per-cycle `try/except` that logs the failure
  with traceback and **re-raises** (crash-loud behavior preserved, now with a record).
- `vinu-live/vinu_live/cli.py` — `worker_main`, `trade_plan_worker_main`,
  `shadow_worker_main`, `feedback_worker_main` converted the same way.

## What I did

1. Verified the audit's "no logging" claim was stale (`setup_logging` existed and was
   wired everywhere).
2. Added a structured JSONL sink to the shared setup rather than a separate new
   framework — consistent with the existing single-`setup_logging` pattern.
3. Converted every unattended worker loop's `print()` cycle events and per-item
   results to `logger.info(...)` with `vinu_ctx`, and wrapped each cycle so a failure
   is **logged with traceback then re-raised** — visibility added, no new
   fail-safe/silent-swallow behavior introduced (per the task's step 6).

## What is achieved

- Shared logging setup lives in `vinu-infra` and is imported by every worker loop
  (unchanged import path; now emits both text and structured JSONL).
- Every worker's exceptions are captured as structured records with a traceback and
  enough context to identify which ticker/artifact/cycle failed (acceptance #1, #2).
- New test proves a forced exception in a worker-style logger produces a structured
  record, not a silent failure (acceptance #3).

## Alignment with plan / justification

- **Followed as written:** shared setup in `vinu-infra`; worker loops wired to it;
  exceptions logged with context; no broader swallowing of exceptions; landed before
  tasks 01/04.
- **Deviations, both deliberate and recorded:**
  1. The task suggested "stdout as structured JSON." I kept stdout as the existing
     human-readable text (entrypoint.sh and manual ops rely on it) and added a
     dedicated JSONL file sink (`VINU_STRUCTURED_LOG`). Strictly more useful for an
     aggregator and non-breaking.
  2. The task's premise (build the substrate from scratch) was already half-done;
     I extended the existing `setup_logging` instead of adding `structlog` or a
     hosted APM. No new external dependency, no cost attached — matching the task's
     own "don't over-engineer" guidance.

## Testing

- `python3 -m pytest vinu-infra/tests -q` → **99 passed** (4 new logging tests +
  95 existing).
- `python3 -m pytest vinu-live/tests -q` → **152 passed** (cli.py edits green).
- `python3 -m pytest vinu-agent/tests -q` → **797 passed** (cli.py edits green).
- `python3 -m py_compile` on all three edited modules passed.

## Notes for downstream tasks

- New workers (tasks 01, 02, 04) should emit via `logging` with `vinu_ctx`, not
  `print`, so they inherit this substrate from day one.
- Set `VINU_STRUCTURED_LOG=/path/to/structured.log` at deployment to enable the
  queryable sink; unset it to stay console/text only.