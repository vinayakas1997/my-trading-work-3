# Phase 6 — Execution Engine + Live Orchestrator

Status: **not started** · Depends on: Phase 3 (book), Phase 4 (frozen trade plan), Phase 5 (circuit breaker) · Blocks: Phase 7

## What it is

The `vinu-live` component that actually runs: a scheduled/event-driven loop reading a Phase 4
frozen trade-plan artifact, evaluating its pre-written entry, sizing, and in-trade contingency
conditions against live market data, checking Phase 5's circuit breaker last, and only then
placing or adjusting an order via a broker/exchange API. This is the first component in the
entire architecture that runs continuously rather than on-demand or to completion — every
existing package (`vinu-research`'s loop, `vinu-agent`'s conversational tools,
`vinu-initial-analysis`'s runner invocations) either runs once per call or waits to be asked.

**Zero LLM calls happen here, and this is now correctly understood as a consequence, not a
limitation:** every decision this phase makes was already made in Phase 4. This phase's entire
job is mechanical — evaluate a condition, execute the matching pre-written rule. If it ever finds
itself needing to *decide* something Phase 4 didn't anticipate, that is a signal the plan was
incomplete, not a case for this phase to improvise.

## Impact

**Before this phase:** Every upstream phase produces correct numbers, gated forecasts, frozen
plans, and enforced limits — but nothing acts on any of it. The system can tell you exactly what
it would do; it does nothing.

**After this phase:** The system executes frozen plans on a schedule, respecting every upstream
gate. Should run first in a paper/shadow environment, comparing realized fills against what
Phase 4's plan predicted, before any real-capital use.

**What still won't work after this phase alone:** Execution places and manages trades but doesn't
by itself feed outcomes back into Phase 2's personality memory or Phase 4's calibration tracking
— that's Phase 7.

## Where changes occur

- New `vinu-live` orchestrator and execution modules — broker/exchange API integration,
  order-state tracking (submitted, filled, partially filled, rejected, cancelled), writing fills
  into Phase 3's book ledger as the **only** writer to that ledger.
- `vinu-agent`'s `TradePlanTool` becomes a consumer of this pipeline's status (a plan currently
  executing, its state, its realized-vs-predicted delta) for conversational summaries, rather
  than the primary interface to any of it.

## Why we need this

This is where the vision stops being analysis, memory, and authored plans, and becomes an actual
trading system. Every upstream phase exists specifically so this one has something trustworthy
to act on before touching a broker API: risk numbers that aren't guessed (Phase 1), personality
context that's confidence-scored (Phase 2), a live book that's accurate (Phase 3), a forecast
proven to have skill and a plan exhaustive enough to need no live judgment (Phase 4), and a hard
ceiling that can't be talked around (Phase 5).

## How to test it

- Shadow-mode test: run the full loop against a paper/shadow environment for an extended period
  before any real-capital test; compare realized shadow fills against Phase 4's plan
  predictions.
- Condition-evaluation test: confirm every contingency rule in a sample of frozen plans
  evaluates correctly against synthetic live-data scenarios designed to trigger each one.
- Order-state test: simulate partial fills, rejections, and broker-side errors; confirm Phase
  3's book always reflects the true state, never an assumed one.
- Breaker-integration test: confirm Phase 5's circuit breaker is checked on every single order
  attempt with no code path that skips it, including any manual/override path.
- No-improvisation test: construct a scenario a frozen plan's contingency rules don't cover;
  confirm the system's behavior is an explicit, logged "no matching rule — halt/escalate," never
  a silent, unplanned decision.
