---
name: phase-2-guard-rail
status: proposed-not-built
purpose: what keeps batched, vinu-portfolio-backed funding robust -- cross-service failure handling, stuck PEND items, and the coupling this phase introduces between vinu-agent and vinu-portfolio.
---

# Phase 2 -- Guard rails

**If `vinu-portfolio` is unreachable, skip funding this cycle -- never
fall back to the old fixed-fraction math silently.** `capital_allocator`
now depends on a real network call to a separate service for its actual
allocation math. Falling back to the old `deflated_sharpe`-only rule when
that call fails would quietly defeat the entire point of this phase --
whoever's monitoring the system would see "funding happened" and have no
way to know it happened on the weaker math. Correct behavior: the `PEND`
batch simply waits for the next cadence attempt, and the failure is
logged distinctly (same fail-loud discipline as Phase 0's RunLog-trigger
guard rail).

**`PEND` age must be visible, even without auto-expiry.** If
`vinu-portfolio` stays unreachable across several cadence cycles, `PEND`
items pile up with nothing funded and no natural place anyone would
notice. This phase doesn't need to decide an auto-expiry policy, but every
`PEND` transition and every skipped cadence attempt must write a
`TickerLedger` (Phase 0) row -- a growing, unfunded `PEND` queue needs to
be something a human can actually see, not a silent internal state.

**Funding is capped at `min(risk_gatekeeper's approved size,
vinu-portfolio's computed size)` -- never above the original approval.**
`vinu-portfolio`'s risk-parity engine may compute a smaller position than
what `risk_gatekeeper` approved (real portfolio-level constraints
tightening what looked fine in isolation) -- that's expected and fine,
fund the smaller amount. It must never fund *more* than what was actually
approved for that specific candidate; the portfolio engine's job here is
sizing down for real constraints, not a second, independent approval that
could expand exposure `risk_gatekeeper` never signed off on.

**Cadence batch boundaries need an explicit, tested rule for the
edge case.** An artifact transitioning into `PEND` at the exact moment a
cadence run starts must deterministically land in either that run or the
next one -- never silently excluded from both because the timestamp
comparison used `>` on one side and `>=` on the other. Pick one rule
(inclusive of the batch's own timestamp cutoff, exclusive of the next)
and be consistent, or an artifact could sit invisible until someone
happens to notice a stuck `PEND` row in `TickerLedger`.

**Watch the runtime call direction between the two services -- it's now
bidirectional, and that needs a timeout, not a redesign.** `vinu-portfolio`'s
drawdown monitor already calls `agent-api`'s `/broker/halt` at runtime
(confirmed in `routes_broker.py`'s own docstring). This phase adds the
reverse call -- `capital_allocator` (inside `agent-api`) calling
`vinu-portfolio`'s allocation endpoint. These are different call shapes
(portfolio's halt call is a one-way emergency signal; this new call is a
synchronous request/response the cadence run waits on) and shouldn't
actually form a cycle within one call chain, but the new call needs an
explicit timeout regardless -- a hung request to `vinu-portfolio` must not
be able to stall the whole cadence run indefinitely.
