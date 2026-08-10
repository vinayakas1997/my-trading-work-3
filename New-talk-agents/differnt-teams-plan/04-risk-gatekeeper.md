---
name: team-risk-gatekeeper
status: proposed-not-built
purpose: design proposal for a new vinu-agent team that approves or rejects a tuned strategy spec against portfolio-level risk rules, immediately before it would go live.
---

# risk_gatekeeper (proposed)

## Role

Last check before a strategy spec becomes a real order: given a tuned
spec from `strategy_tuner`, decide approve or reject against
portfolio-level risk rules — position sizing vs. account size, existing
exposure/correlation to open positions, max concurrent risk — and say
why, not just yes/no.

## Scope & responsibilities

- **In scope**: one strategy spec in, one verdict out — `APPROVED` /
  `REJECTED` (mirrors the `VERDICT: PASS/STOP` pattern `research`'s
  `risk_critic` specialist already uses — same shape, reused rather than
  invented fresh) with the specific rule that drove the decision.
- **Explicitly not in scope**: re-evaluating whether the strategy or its
  parameters are *good* (that's `strategist`/`strategy_tuner`'s job,
  already done upstream) — `risk_gatekeeper` only ever asks "does this fit
  within the portfolio's actual risk limits right now," never "is this a
  smart trade."
- On rejection, the DAG sends it back to `strategist` (see
  [00-overview.md](00-overview.md)) rather than dropping it — a rejected
  spec is a real signal ("size too large for current exposure," say) that
  the next `strategist` pass should account for, not a dead end.

## The real dependency this team is blocked on

Approving/rejecting against "portfolio-level risk" requires actually
knowing current exposure — open positions, their sizes, correlation
between them. That data has to come from somewhere real (the broker /
position-tracking layer, e.g. near `vinu-live/vinu_live/book/schema.py`,
which already has a real `Position` schema per the `pnl_attribution`
design doc). The architecture doc already flags, under "explicitly
deferred," that tool-permission enforcement and the broker wiring are
only a test connection today, not a full restructure. `risk_gatekeeper`
needs a real `get_portfolio_exposure`-style tool backed by real position
data before it can do anything beyond a stub — this is a genuine
prerequisite, not just an implementation detail to fill in later.

## How it adopts to vinu-agent, out of the box

Same manager + specialist shape, `delegate_to_team`. Mechanically nothing
new beyond the missing exposure-data tool above.

## Position in the DAG

Fourth step, the gate before Phase 6 execution. See
[00-overview.md](00-overview.md).

## Open questions

- **Trigger**: is this always a synchronous in-conversation check (the
  user reviewing a proposed trade with the orchestrator), or does whatever
  component actually submits orders call it directly, non-interactively,
  right before submission? These have different implications — an
  in-conversation check can ask the user a clarifying question; a
  submission-time check can't block on a person being present. Not
  decided; likely needs to support both, but which is the default matters
  for how strict `manager_prompt.md` should be about ever asking a
  follow-up question versus always returning a hard verdict.
- Depends on real portfolio-exposure data existing (above) — currently
  blocked, same category of gap as the broker wiring the architecture doc
  already deferred.
