# Problem: Chapter 2 of the pre-analysis book -- "Experience"

## Scope (settled 2026-09-23)

This folder owns Chapter 2 of the pre-analysis book (see
`gatekeeper-initial-analysis/01-plan.md` for the full 2-chapter
structure). Strictly bounded to the same real historical range the book
covers (2022-01-01 -> the pre-analysis end date) -- nothing live/ongoing
past that boundary belongs here (e.g. the 7-day trailing paper-trade
rehearsal in `vinu_research/loop.py` is live, not historical, so it's
out of scope for this chapter).

Two sub-chapters:
- **2b. Shadow evaluator -- FIRST FOCUS**, by explicit direction.
- **2a. Simulation recorded results** -- second.

This ordering is deliberate, not arbitrary: 2b turns out to be mostly a
wiring problem (the data already exists, just isn't exposed through the
book), while 2a is a real, harder capture problem (the data genuinely
doesn't exist yet). Cheapest real win first.

## 2b. Shadow evaluator -- what's actually true (corrected finding)

Original assumption going into this session was that shadow-evaluator
data isn't recorded at all. **That's wrong, checked against the real
code.** `vinu-live/vinu_live/shadow_evaluator.py::_write_shadow_
evaluation` already writes every shadow-evaluation verdict into
`StrategyEvaluationStore` (`vinu-infra/strategy_evaluation.py`) via
`write_step_result(step_name="shadow_evaluator", step_order=6, verdict,
reasoning, metrics)` -- this is the same real audit-trail database built
in this session's earlier strategy-enhancer work
(`missing-pieces-of-system/startegy-enhancer/`). `StrategyEvaluationStore.
get_history(artifact_id)` already returns the full step-by-step verdict
history, shadow_evaluator included.

So the real gap for 2b is NOT "build recording from scratch" -- it's
**"this data lives in its own separate store, never exposed through the
book."** The exact same "separate place, not shared" pattern already
found and flagged for the Calibration Tracker in `gatekeeper-initial-
analysis/problem-explanation.md`. Closing this is mostly a matter of the
gatekeeper's `chapter="experience"` reading `StrategyEvaluationStore.
get_history()` (scoped to the artifacts/tickers relevant to the
pre-analysis window) and shaping it the same way the other chapters are
shaped -- much closer to "wire it in" than "invent a new mechanism."

## 2a. Simulation recorded results -- what's actually true

Checked `vinu-research`'s real result types (`WalkForwardResult`,
`HoldoutResult`, `StressWindowResult`, `PaperRehearsalResult`,
`ResearchResult` in `models.py`) -- these carry aggregate metrics per
trial (returns, drawdown, sharpe-shaped numbers), not a persisted
trade-by-trade or bar-by-bar record of what happened *during* one
simulation run. Once a trial's aggregate result is computed, the
intermediate path that produced it isn't kept. This is the real,
still-genuinely-missing piece -- the original concrete example that
motivated this whole folder (Cluster A's `kalman_filters` vs.
`arima`/`exponential_smoothing` relationship over a simulation window)
needs this kind of intermediate detail to ever be checkable, and it
doesn't exist today.

## Why 2a shouldn't be built as pattern-matching, only as capture

This project already has a direct precedent for not building
interpretation ahead of data. The screener round-2 plan explicitly
scoped OUT a weight-adjuster/feedback-loop mechanism for the same
reason: *"there's no honest way to test a weight-adjustment mechanism
against data that doesn't exist yet."* Same logic here: 2a should be
built as pure, structured CAPTURE of intermediate simulation state
(what happened, tied to a real ticker/timestamp/simulation window,
comparable and queryable later) -- not as a mechanism that already tries
to compare current conditions against past ones and surfaces "this
looks like that" as a hint. That comparison layer needs real historical
outcomes to validate against first, which won't exist until capture
itself has been running for a while.

## Not yet designed

This file is the problem statement only. 2b's real design (how
`StrategyEvaluationStore.get_history()` gets shaped into the
gatekeeper's `chapter="experience"` response) and 2a's real design
(what intermediate simulation state gets captured, where it's stored)
are both separate, not-yet-written plans -- 2b first, per the stated
priority.
