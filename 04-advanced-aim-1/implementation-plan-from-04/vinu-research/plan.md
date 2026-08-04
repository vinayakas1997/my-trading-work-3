---
name: vinu-research-plan
component: vinu-research
status: implemented
---

# vinu-research — Scheduler Hosting for the Freshness Recompute Job

## What the plan is

**Decided and implemented**: the recompute job from
`../vinu-initial-analysis/plan.md` is hosted here, not as a new small
executor in `vinu-initial-analysis`. Added `regime_recompute_scan()` to the
existing `ScheduledResearchExecutor`
(`vinu-research/vinu_research/scheduled/executor.py`), following the exact
shape of its already-real `decay_scan()`/`revalidation_scan()` — called from
`_run_loop()` on its own daily interval, distinct from the hourly cadence
the other two use.

## Why

`../../04-vinu-components-integration-plan.md` §3 confirmed this executor
already exists and already runs two genuinely analogous periodic checks —
"is this stale/degraded, and if so trigger a refresh," just applied to
strategies instead of regime/correlation features. Reusing it instead of
building a parallel scheduler in `vinu-initial-analysis` avoids two
different services independently reinventing "poll on an interval, dispatch
due work."

## Impact

Chosen as the host: no new executor, no new job-store schema, just one more
scan function in an `_run_loop()` that already existed and already ran
hourly. The tradeoff — a cross-service call from `vinu-research` into
`vinu-initial-analysis`'s `/analysis/run/...` route rather than
`vinu-initial-analysis` calling its own route locally — was accepted as
cheaper than standing up a second scheduler.

## What decision-dots this connects to for the future

- **Decided**: this was genuinely an either/or with
  `vinu-initial-analysis/plan.md` — implemented here; `vinu-initial-
  analysis/plan.md` updated to "not needed there, see this file."
- Reuses the exact cadence/error-handling shape already established for
  `decay_scan`/`revalidation_scan` (try/except per-symbol, log-and-continue
  on failure, one bad symbol never blocks the rest) — no third style
  introduced.

## Implementation

- `regime_recompute_scan()` on `ScheduledResearchExecutor`
  (`vinu_research/scheduled/executor.py`): reuses the same universe-
  discovery pattern as `decay_scan`/`revalidation_scan`
  (`strategy_store.list_artifacts_by_statuses([ACTIVE, MONITORING])`,
  deduped `art.universe` symbols), then `POST`s to
  `{correlation_api_url}/analysis/run/{symbol}?angle_names=regime_analysis`
  for each — a genuine cross-service HTTP call via `httpx.AsyncClient`, not
  a local import. Guarded by a new `regime_recompute_interval_days` config
  field (default 1, matches the daily-not-hourly reasoning above; `<= 0`
  disables it, same convention as `revalidation_interval_days`).
- `_run_loop()` gained a third interval (`regime_recompute_interval =
  86400.0` — once per day) alongside the existing hourly `decay_interval`/
  `revalidation_interval`.
- `vinu_research/config.py` — new `regime_recompute_interval_days: int = 1`
  field + `VINU_RESEARCH_REGIME_RECOMPUTE_INTERVAL_DAYS` env override,
  following the exact pattern of `revalidation_interval_days`.
- `correlation_api_url` (already in `ResearchConfig`, default
  `http://127.0.0.1:8083`) is reused as the `vinu-initial-analysis` base
  URL — it already pointed there for `ResearchTools`'s `_correlation_client`
  — no new config field needed for the target service.

## Files touched, bugs, and fixes

Tracked in [`status.md`](status.md), not here.
