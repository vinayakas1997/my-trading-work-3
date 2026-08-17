---
name: implementation-status-vinu-tools
status: not-started
purpose: tracks real code changes made to vinu-tools, if any — reuse-only per the plan.
---

# vinu-tools — Implementation Status

## What's built

Nothing yet — no changes made in this phase.

## Plan

Per `../04-build-status.md` and `../05-angle-reconciliation.md`,
vinu-tools is reuse-only: `shock_clustering`/`shock_personality`
(vinu-initial-analysis angles) already call into
`vinu_tools.compute.risk.{covariance,volatility}` for real, working
covariance and GARCH logic. The plan is to call this same code from a
new standalone `garch` angle (method `26-garch` from the 32-list) rather
than reimplementing GARCH — no changes to vinu-tools itself are expected
unless that extraction surfaces a signature/output-shape mismatch.

## Not yet done

Everything — this component hasn't been touched. Revisit once Phase 4
(angle reconciliation execution) reaches the `garch` extraction step.
