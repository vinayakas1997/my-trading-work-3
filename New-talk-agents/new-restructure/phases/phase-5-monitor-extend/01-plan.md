---
name: phase-5-plan
status: proposed-not-built
purpose: deep-dive plan for Phase 5 -- NOT a new build. Extending vinu-live's already-real TradePlanOrchestrator with the specific pieces it's genuinely missing, instead of standing up a competing Monitor authority inside vinu-agent.
---

# Phase 5 -- Monitor (extend, not build)

## Correction to the original mermaid-doc framing

`mermaid-explanation.md` originally marked `MON` ("Monitor") `<i>new</i>`,
"sole authority on live-position close/hold." Confirmed by reading
`vinu-live` directly: `trade_plan/orchestrator.py`'s
`TradePlanOrchestrator` already owns entry, invalidation-exit, and
contingency actions every cycle (via `condition_evaluator.py` +
`live_metrics.py`, checking `breaker/engine.py` before every order). That
**is** sole authority over a live position's lifecycle, already built.
Building a second Monitor inside vinu-agent would recreate, one layer up,
the exact "two things can independently close the same position" bug
this design already fixed once (Monitor vs. the rebalancer in the
original framing). `feedback_loop.py` also already writes closed-position
outcomes back to research calibration, `pnl_attribution`, and refreshes
shock-personality angles -- a real chunk of "post-trade review" already
exists too.

## What's genuinely missing, confirmed by what `feedback_loop.py`'s
## described writes do *not* cover

1. **`HypothesisRegistry` write.** `feedback_loop.py` writes to research
   calibration, `pnl_attribution`, and shock-personality angles -- none of
   those is `HypothesisRegistry`, which is specifically what the
   Planner's mandatory pre-proposal consult reads. Without this, a
   decayed/dropped strategy's specific failure reason still isn't visible
   to the next proposal on that ticker, even after this phase's other
   fixes land.
2. **`TickerLedger` write.** Brand new as of Phase 0 -- nothing writes to
   it yet by definition. Every check, decay signal, and close-out
   narrative needs its own `TickerLedger` row.
3. **Shock-angle event trigger.** `shock_clustering`/`shock_personality`
   angles already exist (`vinu-initial-analysis`) but nothing currently
   triggers an off-cycle check when one fires -- confirm whether
   `TradePlanOrchestrator` runs strictly on a timer today; if so, this
   phase adds an event-driven path alongside it, not instead of it.
4. **Rebalance-request intake.** Phase 2's `capital_allocator` rebalancer
   sends a *request* ("unwind X to fund Y"), not a direct action -- but
   confirmed nowhere yet that `TradePlanOrchestrator` has any method that
   accepts such a request as an input to its next cycle's decision. This
   is the actual wiring gap, not "build a Monitor to receive it."

## What Phase 5 builds

**1. Wire `feedback_loop.py`'s existing close-out path to also write
`HypothesisRegistry.add_evidence(...)` and a `TickerLedger` row**, using
the same tag conventions already established (`source="watchlist"` vs.
whatever this path's natural source value is). Reuses the exact method
Monitor was always going to call in the original framing -- just calling
it from the code that already runs the close-out, instead of new code.

**2. Add a rebalance-request intake point on `TradePlanOrchestrator`** (or
a thin new module beside it) that Phase 2's `capital_allocator` can call.
The request folds into the orchestrator's own next-cycle evaluation
alongside its existing invalidation/contingency checks -- it does not
bypass the orchestrator's authority, it becomes one more input to it.
This is what actually enforces "the rebalancer can only request, never
act directly" at the code level, not just in prose.

**3. Add the shock-angle trigger** -- an off-cycle check invoked when
`shock_clustering`/`shock_personality` fires for a symbol with open
positions, running the same evaluation `TradePlanOrchestrator` already
does on its normal cycle, just off-schedule.

**4. Confirm and, if missing, add batching/prioritization across open
positions.** `mermaid-explanation.md`'s original efficiency pass assumed
Monitor needed to batch multiple positions into fewer calls and
prioritize ones showing early decay/volatility. **Read
`TradePlanOrchestrator`'s real per-cycle loop before implementing this
item** -- if it already evaluates all open positions in one pass
efficiently, this item is already done and this phase skips it; if it's
one-call-per-position, this phase adds the batching the original design
called for.
