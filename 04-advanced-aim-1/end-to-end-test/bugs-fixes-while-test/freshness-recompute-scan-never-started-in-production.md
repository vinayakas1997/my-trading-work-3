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

**Later correction — confirmed against the real stack, and it crashed on
first run.** When `01-setup-and-rebuild.md`'s rebuild was actually run
against Docker (2026-08-04), `schedule-freshness` crashed on startup with
`OSError: [Errno 30] Read-only file system: '/nonexistent'`. Root cause:
`ScheduledResearchJobStore()` (`vinu-research/vinu_research/scheduled/store.py:14-15`)
defaults to `Path.home() / ".vinu" / "scheduled_research"` when constructed
with no explicit `path`, and `schedule_freshness_main` (this fix, above)
called `ScheduledResearchExecutor(service=service)` without passing a
`store=`, so it fell through to that default. Inside the container, the
`app` user (uid 100, added via `addgroup`/`adduser --system`) has no real
passwd home directory, so `Path.home()` resolves to `/nonexistent` —
exactly the same failure shape `end-to-end-complete-status.md` already
found for `vinu-agent` falling back to `Path.home()/".vinu"` when
`VINU_AGENT_DATA_ROOT` was unset, just recurring here in code this fix
itself added. Because this only crashed the background `&` process, not
the `exec`'d foreground HTTP server, `docker compose ps` kept reporting
`healthy` throughout — the crash was silent to every check except reading
the container logs directly.

Fixed in `vinu-research/vinu_research/cli.py`'s `schedule_freshness_main`:
now calls `load_config().data_root` (already imported and used elsewhere
in this file) and constructs an explicit
`ScheduledResearchJobStore(data_root / "scheduled_research" / "jobs.json")`,
passed to `ScheduledResearchExecutor(store=store, service=service)` instead
of relying on the no-args default.

**Second, separate bug found investigating why this fix's own log check
(directly below) showed nothing even before the crash was noticed**: the
`docker compose logs vinu-research | grep "schedule-freshness"` command
this file itself prescribes found zero lines — not because the loop wasn't
running, but because `vinu-research schedule-decay/schedule-freshness &`
are separate Python processes whose stdout, when piped (as `docker logs`
always is, never a tty), is fully block-buffered by default. Their
`print()` startup banners (a few dozen bytes each) sit under Python's
default buffer size and were never flushed — the check in this file would
have reported "nothing happened" indefinitely even on a fully healthy
loop. Confirmed the same pattern exists project-wide: `vinu-live`'s
trade-plan/feedback/generic workers, `vinu-news`'s ingest loop, and every
other `entrypoint.sh` background `&` job all use raw `print()` for their
startup/cycle banners with no `PYTHONUNBUFFERED` set anywhere in the repo
— only `vinu-research/Dockerfile` was fixed this pass (added
`ENV PYTHONUNBUFFERED=1`), since it's the one this session's work depends
on; the same fix for the other five services is flagged, not applied, to
avoid unrequested changes to services outside this session's scope.
Verified after the fix: both startup lines and the first `revalidation_scan:
0 artifacts re-validated` line appeared in `docker compose logs` within
seconds of container start.

Original text below, describing the fix as made and tested outside Docker
— left as-is for the record; superseded by the correction above.

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
