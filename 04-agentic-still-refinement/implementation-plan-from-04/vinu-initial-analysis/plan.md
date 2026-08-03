---
name: vinu-initial-analysis-plan
component: vinu-initial-analysis
status: signal-usage-contract-implemented
---

# vinu-initial-analysis — Signal-Usage Contract + Freshness Recompute Job

## What the plan is

Two distinct pieces of work that both live in this component:

1. **Signal-usage contract** — tag each angle's output (`significance_score`,
   `regime_features`, correlation structure) with what it's actually
   proven to support — e.g. `proven_for: significance`, `not_proven_for:
   direction` — as provenance metadata traveling with the value itself,
   not as separate prose only a human reads.
2. **Freshness recompute job** — a scheduled job that recomputes regime/
   correlation features on a cadence (daily, not hourly — regime moves
   slower than a strategy's rolling Sharpe), independent of whether any
   agent session happens to be running.

## Why

Question 6 from `../../01-vinu-questions-prompt.md` ("which strategy
today") needs to know which signals can actually support the kind of call
being made. Right now that boundary — direction prediction from sentiment
tested twice at ~50% coin-flip, `significance_score` proven for magnitude/
surprise, not direction — exists only as prose in
`01-the-stage-2-claude/full-plan.md`. Nothing stops a future strategy rule
from misusing `significance_score` for direction anyway, because the
constraint doesn't travel with the data.

Separately, regime/correlation data genuinely goes stale — `../../03-
question-entity-mapping-and-freshness.md` classified it "periodic
reanalysis," and Decision 2 in that file settled that staleness cannot be
the agent's responsibility to notice; something has to actually recompute
it on a schedule.

## Impact

The signal-usage contract closes a real, previously just-documented risk
(a proven-negative signal being reused for the one thing it's proven not
to do) at the data layer, where it can't be forgotten or reworded away.
The recompute job closes the other half of Decision 2 — the "who triggers
this" question — confirmed in `../../04-vinu-components-integration-plan.md`
§3 to have a working precedent already (`vinu-research`'s
`ScheduledResearchExecutor`, `decay_scan`/`revalidation_scan`).

## What decision-dots this connects to for the future

- The signal-usage contract's tags are one of the Facts & Limitations
  Registry's (`../vinu-agent/plan.md`) source writers — this component
  writes the row, `vinu-agent` surfaces it.
- **Decided**: the recompute job is hosted in `vinu-research`'s existing
  `ScheduledResearchExecutor` (`regime_recompute_scan()`), not as a new
  executor here — see `../vinu-research/plan.md` for the implementation.
  This component's job here is done; no recompute executor needed in this
  codebase.
- The `AlmgrenChrissCostModel`/`compute_full_metrics` reuse discipline
  already established for `vinu-simulator` in prior plans (never
  reimplement, always import) is the same discipline to apply here: reuse
  the existing `/analysis/run/{symbol}?angle_names=...` route
  (`server/routes_read.py`) as the recompute mechanism, don't build a
  parallel compute path.

## Implementation

- **Signal-usage contract**: extend each angle's stored output schema
  (wherever `significance_model.py`/`regime_features.py` write their
  result) with `proven_for`/`not_proven_for` fields — populated once from
  what's already tested (`01-the-stage-2-claude/testing-status/
  significance-classifier-improvement/test-log.md`'s AUC results, the
  direction-prediction coin-flip finding), not new research.
- **Recompute job — implemented in `vinu-research`, not here.** The
  existing `POST /analysis/run/{symbol}?angle_names=regime_analysis` route
  (`server/routes_read.py`) is the mechanism `vinu-research`'s
  `regime_recompute_scan()` calls; this component needed no code changes
  for the recompute side beyond already exposing that route.

## Files touched, bugs, and fixes

Tracked in [`status.md`](status.md), not here.
