---
name: structured-logging
closes: "production-grade" gap raised in conversation (2026-08-17) — no structured logging/error tracking found anywhere in vinu-components
status: complete — see [10-structured-logging-status.md](10-structured-logging-status.md) (2026-08-17)
priority: cross-cutting foundation, sequence alongside/before tasks 01 and 04
---

# Task: add a structured logging / error-capture substrate

## Goal

Give every service and worker in `vinu-components` a consistent way to emit structured, queryable,
timestamped log and error records — so a failure is recorded somewhere, not just visible if someone
happens to be watching stdout when it happens.

## Why

Grepped the whole `vinu-components` tree for `structlog`, `logging.config`, `JSONFormatter`, `Sentry` —
zero hits, anywhere. There is currently no way to know a worker silently died overnight, no centralized
place to see "the significance-worker has been failing for 6 hours," no error aggregation across
services. This matters more than usual here because tasks 01 and 02 in this plan add *more* unattended,
scheduled workers (`capital-allocator-worker`, a scheduled `ShadowEvaluator` call) — shipping those
without this substrate first means they can fail silently from day one.

**This is purely backend infrastructure — no agent, no LLM, no polling logic.** A later, separate task
(not written yet, deferred per the user) will add a Jarvis-like watcher-agent that reads what this
produces and decides what's worth surfacing. That agent has nothing useful to poll until this exists.

## Current state (verified 2026-08-17)

- No structured logging library in use anywhere in the tree (confirmed by grep).
- Workers (`planner-worker`, `significance-worker`, `skill-audit-worker`, `trade-plan-worker`,
  `feedback-worker`, `shadow-worker` per `entrypoint.sh` in `vinu-agent` and `vinu-live`) presumably use
  plain `print`/default `logging` module calls or nothing at all — confirm exactly what exists today by
  reading a couple of worker-loop implementations before designing the replacement.
- Health-check routes do exist in several services (`vinu-initial-analysis/vinu_initial_analysis/
  server/routes_config.py`, `vinu-news/vinu_news/server/routes_read.py`, `vinu-simulator/vinu_simulator/
  server/routes_read.py`, and others) — these are a reasonable model for "does this service respond,"
  but say nothing about what happened inside a worker loop's most recent cycle.

## Steps

1. Read a representative worker-loop implementation (e.g. `planner_worker_main` in `vinu-agent/
   vinu_agent/cli.py`) end to end to see exactly what error handling exists today (bare `except`, logged
   and continue, or something else).
2. Pick a structured-logging approach consistent with this being a multi-package Python monorepo —
   `structlog` or Python's built-in `logging` with a JSON formatter are both reasonable; don't over-engineer
   with a hosted APM/Sentry integration unless there's already an account/budget for one — check with
   whoever owns ops decisions before adding an external dependency with a cost attached.
3. Add a shared logging setup (likely belongs in `vinu-infra`, since that's already the shared-package
   home for cross-cutting concerns like the LLM client and the security scanner/SSRF guard) that every
   other package can import and configure consistently — one log format, one place each event lands
   (stdout as structured JSON is sufficient for now; a log aggregator can tail that later without any
   code change).
4. Wire every existing worker loop (all six in `entrypoint.sh` plus whichever new ones tasks 01/02 add) to
   use this logging setup, replacing ad-hoc print/logging calls. At minimum, log: worker start, each
   cycle's start/end with duration, any exception with full traceback, and specifically anything currently
   caught and silently continued.
5. Make sure exceptions inside a worker's per-item loop (e.g. one ticker failing inside a batch) are
   logged with enough context to identify *which* item failed, not just "an error occurred."
6. Do NOT swallow exceptions more broadly than before — the goal is visibility, not new fail-safe
   behavior. If a worker currently crashes loudly on a bug, it should still crash loudly; it should just
   also produce a structured record before or as it does so.

## Acceptance criteria

- A shared logging setup exists in `vinu-infra` (or wherever step 3 lands it) and is imported by every
  worker loop, not reimplemented per-service.
- Every worker's exceptions are captured as structured records with a traceback and enough context (which
  ticker/artifact/candidate was being processed) to diagnose without re-running.
- A test or manual check confirms: killing a worker's underlying call mid-cycle (e.g. force an exception
  in a test double) produces a structured log record, not a silent failure.
- This lands before or alongside tasks 01 and 04, so the new capital-allocator-worker and the new
  rebalance route are built with logging from day one, not retrofitted.

## Dependencies

None to start. Tasks 01, 02, and 04 should be sequenced to land on top of this, not before it — new
unattended surface area should be born with logging already wired in.
