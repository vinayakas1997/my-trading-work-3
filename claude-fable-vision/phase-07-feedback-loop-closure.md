# Phase 7 — Feedback-Loop Closure

Status: **not started** · Depends on: Phase 2 (personality angles), Phase 4 (forecast/plan authoring), Phase 6 (execution) · Blocks: none (final phase)

## What it is

The write-back path that keeps Phase 2's personality memory and Phase 4's calibration tracking
from going stale once real trades start happening — reusing the pipe the architecture already
defines (*"Live-Trading produces execution logs → consumed by Initial-Analysis for PnL
attribution"*) rather than inventing a new one. Two updates flow through it:

1. **Into `vinu-initial-analysis`'s existing `pnl_attribution` angle** (currently dormant per the
   architecture doc, "until Live-Trading") — execution logs from Phase 6 become its first real
   input. A realized shock event also updates Phase 2's `gap_fill_rate`/`vol_persistence`/
   `shock_cluster_membership` stats and narrows their confidence intervals with the new
   observation.
2. **Into `vinu-research`'s existing `decay_monitoring`/decay-scan** — realized forecast
   direction/magnitude vs. Phase 4's prediction, and realized volatility vs. Phase 1's estimate
   at entry, update the forecast's calibration-gate status the same way decay-scan already
   tracks strategy Sharpe decay.

Critically, this is **not** a live re-decision loop — it feeds the *next* Research-Simulations
cycle (the next time Phase 4 authors or revises a plan for that symbol), never a mid-trade
judgment call. That distinction is what keeps this phase consistent with "zero LLM calls in
Live-Trading": the loop closes at the next research cycle, not inside the running trade.

## Impact

**Before this phase:** Phase 2's personality stats and Phase 4's calibration tracking are built
once and never updated by what actually happens live — memory goes stale the same way the
original architecture worries price/news data goes stale, just for behavioral and forecast-skill
stats instead of raw data freshness. `pnl_attribution` stays dormant indefinitely.

**After this phase:** The system is a closed loop end to end. A new shock updates the relevant
symbol's personality stats. A forecast's realized accuracy continuously updates its
calibration-gate status. `pnl_attribution` goes from a stub to a real, populated angle.

**What still won't work after this phase alone:** This closes the loop for the components built
in Phases 1–6; extending it to strategies or symbols outside this vision's scope would be a
follow-on, not part of this phase.

## Where changes occur

- New write path from `vinu-live`'s execution logs (Phase 6) into `vinu-initial-analysis`'s
  `pnl_attribution` angle and into Phase 2's angle storage (targeted stat updates, not full
  recomputation on every tick).
- New write path into `vinu-research`'s existing `decay_monitoring`/decay-scan mechanism (the
  same `schedule-decay` CLI pattern the architecture doc's timeline already built for strategy
  health) extended to also track forecast calibration.
- No new package required — this phase is primarily wiring existing components (Phases 2, 4, 6)
  to write back to each other through pipes the architecture already names.

## Why we need this

Every other phase in this plan computes something from *current* state. Without this phase,
"current" for personality stats and calibration tracking silently ages from the moment those
numbers were first computed — exactly the staleness problem the architecture's downhill/uphill
data-flow design exists to prevent for price and news freshness, just unaddressed here until now.
This phase is what makes personality and calibration self-correcting from real outcomes instead
of static assumptions that quietly go wrong.

## How to test it

- Update-on-outcome test: a realized shock event for a symbol correctly updates that symbol's
  Phase 2 stats (and narrows its confidence interval) without affecting unrelated symbols.
- Calibration-drift test: a sequence of realized forecast outcomes that starts accurate and then
  degrades correctly flips Phase 4's calibration gate to failing, verifying the write-back path
  specifically (not just Phase 4's own read-side drift test).
- `pnl_attribution` population test: a batch of synthetic execution logs correctly populates the
  angle's expected fields, moving it from stub to real data.
- End-to-end test: seed a full cycle (entry → shock event → realized outcome → angle/calibration
  update) and confirm every downstream field reflects the update, and confirm no code path in
  this phase triggers a live, in-trade decision — only updates consumed at the next research
  cycle.
