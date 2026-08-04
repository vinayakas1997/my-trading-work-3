---
name: freshness-recompute-scan-never-started-in-production
status: fixed
severity: mechanism-fully-built-and-tested-but-never-runs
---

# Bug: the Freshness Contract's recompute job — `regime_recompute_scan()` — was fully implemented and tested but never actually started anywhere in the deployed system

## What was wrong

[`stale-freshness-job-status-initial-analysis.md`](stale-freshness-job-status-initial-analysis.md)
already corrected a documentation claim that this job was "not started" —
the fix there confirmed `regime_recompute_scan()` exists, is hosted in
`vinu-research`'s `ScheduledResearchExecutor`
(`vinu-research/vinu_research/scheduled/executor.py:178-220`), and has real
tests (part of the 489→500 test-count increase). All of that is true. What
that correction did not check, because it was a doc-consistency fix, not a
runtime one: **whether anything in the actually-deployed container ever
constructs and starts a `ScheduledResearchExecutor` at all.**

It doesn't. Found by static code review (grep + read, no Docker run
needed):

- `ScheduledResearchExecutor` is instantiated **nowhere** in
  `vinu-research`'s source outside its own test file
  (`vinu-research/tests/test_scheduled.py`).
- `vinu-research/vinu_research/server/app.py`'s `create_app()` only wires
  HTTP routers — no lifespan hook, no background task, nothing that ever
  calls `ScheduledResearchExecutor(...).start()`.
- `vinu-research/entrypoint.sh` (the container's actual startup command)
  ran exactly one background loop: `vinu-research schedule-decay
  --interval-hours 24 &` — a **separate, hand-written CLI implementation**
  of decay-scanning (`cli.py`'s `schedule_decay_main`/`_run_decay_scan`),
  not the executor's own `decay_scan()` method.

Net effect: `regime_recompute_scan()` — the mechanism
`03-question-entity-mapping-and-freshness.md` §4 (the Freshness Contract)
and `04-vinu-components-integration-plan.md` §3 both describe as the
recompute half of the freshness story — was fully built, fully tested in
isolation, and **never actually ran in the real system**, in exactly the
same "looks done, isn't" shape as this project's other doc-staleness bugs,
except this one wasn't a documentation claim at all — the docs (after the
earlier fix) were accurate about the code existing; the gap was purely
"exists and tested" vs. "actually scheduled to run."

**Second, related finding surfaced while investigating this**: `vinu-research`
now has **two independent, divergent decay-scan implementations** —
`cli.py`'s `_run_decay_scan` (uses `DecayThresholds`, `compute_decay_snapshot`/
`compute_strategy_decay_snapshot`, `transition_status`, actually running in
production via `entrypoint.sh`) and `ScheduledResearchExecutor.decay_scan()`
(uses a hardcoded 0.5 Sharpe-ratio-vs-initial threshold, calls
`service.refresh_strategy()`, never run). They were not caught diverging
against each other before now because the second one never executes.

## Why it mattered

Any downstream freshness read (the agent-side `FreshnessChecker` injected
via `ContextBuilder`, per `04-vinu-components-integration-plan.md`'s design)
depends on regime/correlation data actually being recomputed on a cadence.
Without this job running, regime data across the whole system is stale from
whenever it was last manually triggered — indefinitely — and the
`FreshnessChecker`'s `STALE` label (which reads a timestamp against a
threshold, per the Freshness Contract's read/compute split) would
eventually flag *everything* as stale, not just genuinely old data, since
nothing was ever refreshing it. A rollup status table reading "recompute
job: implemented" would be technically true and practically misleading —
this is the same failure shape as `bug-count-mismatch-in-implementation-agents.md`
and `stale-test-counts-in-e2e-agents.md`, just at the runtime layer instead
of the documentation layer.

## What was fixed

Did not start the full `ScheduledResearchExecutor._run_loop()`, because
that would also start its divergent `decay_scan()` implementation running
concurrently with the one already live via `schedule-decay` — two different
decay policies acting on the same `strategy_store.db` is a new bug, not a
fix. Instead, added a narrower, additive CLI command that runs only the two
scans this Freshness Contract actually needs:

- `vinu-research/vinu_research/cli.py`: new `schedule-freshness` subcommand
  (`schedule_freshness_main`), constructs one `ScheduledResearchExecutor`
  and loops calling `revalidation_scan()` (default: hourly) and
  `regime_recompute_scan()` (default: daily) directly — the same cadence
  `_run_loop()` already hardcodes for these two scans — without touching
  `decay_scan()` or the job-dispatch (`tick()`/`dispatch()`) machinery.
- `vinu-research/entrypoint.sh`: added `vinu-research schedule-freshness &`
  alongside the existing `schedule-decay` background loop.

Reconciling the two divergent `decay_scan()` implementations is explicitly
**not** done here — that's a separate, larger decision (which policy is
correct, or whether to merge them) than this fix's scope; flagged for a
future pass, not silently dropped.

**Verified**: `python -m pytest vinu-research/tests` — 548 passed, 1
skipped, no regressions. Smoke-tested `schedule-freshness` directly (fresh
local data root, no Docker): fires both scans immediately on startup
(matching `schedule-decay`'s existing "run once, then wait" behavior), logs
a per-scan count, does not crash on an empty store or unreachable
`correlation_api_url` (both scans already wrap their body in
`try/except`+log, per the existing code at `executor.py:174/218`).

## What was achieved

The Freshness Contract's recompute half now actually runs in the deployed
system, not just in its own test file. `regime_recompute_scan()` will now
keep regime/correlation data fresh on a real cadence, and
`revalidation_scan()` will now actually re-validate stale strategy
artifacts — both previously silent no-ops in production despite passing
unit tests.

## What to check when this folder's Docker-based verification next runs

Not yet confirmed against the real running stack (this fix was made and
tested outside Docker) — when `end-to-end-test/01-setup-and-rebuild.md` is
next run, add this check:

```bash
docker compose logs vinu-research | grep "schedule-freshness"
```

Expect to see the startup line (`[schedule-freshness] revalidation every
1h, regime-recompute every 24h...`) and, within the first minute, one
`revalidation_scan: N artifacts re-validated` and one
`regime_recompute_scan: N symbols recomputed` line — confirming the process
actually started and completed a real cycle against the live stack, not
just that the container is up. If `N symbols recomputed` stays `0` across
multiple days despite ACTIVE/MONITORING strategy artifacts existing, check
`VINU_CORRELATION_API_URL` is reachable from the `vinu-research` container
(the scan silently logs a warning and moves on per-symbol on failure,
per `executor.py:213-217` — it will not crash, so this needs an explicit
log check, not just "container still running").
