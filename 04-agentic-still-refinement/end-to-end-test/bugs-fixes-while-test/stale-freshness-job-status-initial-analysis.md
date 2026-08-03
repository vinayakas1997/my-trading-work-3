---
name: stale-freshness-job-status-initial-analysis
status: fixed
severity: documentation-staleness
---

# Bug: `vinu-initial-analysis/status.md` said the recompute job was "not started," contradicting its own `plan.md`

## What was wrong

[`implementation-plan-from-04/vinu-initial-analysis/status.md`](../../implementation-plan-from-04/vinu-initial-analysis/status.md)
opened with:

> "**Status: signal-usage contract implemented.** Freshness recompute job
> not started."

and further down:

> "Freshness recompute job (daily regime/correlation recompute): not
> started — pending the either/or decision with `vinu-research/plan.md`."

Both lines directly contradict that file's own sibling,
[`plan.md`](../../implementation-plan-from-04/vinu-initial-analysis/plan.md),
which says the either/or was **decided and implemented**:

> "**Decided**: the recompute job is hosted in `vinu-research`'s existing
> `ScheduledResearchExecutor` (`regime_recompute_scan()`), not as a new
> executor here... This component's job here is done; no recompute
> executor needed in this codebase."

And [`vinu-research/status.md`](../../implementation-plan-from-04/vinu-research/status.md)
independently confirms the job is built and tested there
(`regime_recompute_scan()`, 4 new tests, part of the 489→500 test-count
increase).

## Why it mattered

Read on its own — which is exactly how a `status.md` file is meant to be
read, per this project's own two-file-split convention
(`plan.md` = design, `status.md` = build log) — this line says the work is
outstanding. Someone checking only this file (not cross-referencing its
own `plan.md` or `vinu-research`'s files) would wrongly conclude the
Freshness Contract's recompute half is still an open task, when it's
actually fully shipped, just in a different component's codebase. This is
the same class of mistake the `vinu-components-integration-plan.md`
decision process was explicitly designed to avoid — a status claim that's
stale relative to a decision made after it was written.

## What was fixed

In [`vinu-initial-analysis/status.md`](../../implementation-plan-from-04/vinu-initial-analysis/status.md):

- The opening status line now reads: "Freshness recompute job: decided and
  implemented, but hosted in `vinu-research` instead of here — no code
  lands in this component for it," with a link to
  `vinu-research/status.md`.
- The "Files touched" section's "not started — pending the either/or
  decision" line now reads: "decided and implemented, hosted in
  `vinu-research`," naming `regime_recompute_scan()` and the route it
  calls, with the same cross-link.

## What was achieved

The file can now be read on its own — without needing to already know
about the cross-component decision — and give an accurate picture:
signal-usage contract done here, recompute job done, just not in this
component's own codebase. No claim in this file contradicts its own
`plan.md` anymore.
