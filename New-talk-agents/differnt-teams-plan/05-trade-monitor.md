---
name: team-trade-monitor
status: proposed-not-built
purpose: design proposal for a new vinu-agent team that periodically re-checks an OPEN position against fresh angle data while a trade is live -- the "active during the trade" team, and the first of two teams that don't fit the plain user-triggered delegate_to_team shape.
---

# trade_monitor (proposed)

## Role

While a position from `risk_gatekeeper`-approved execution is open,
periodically re-check it: has anything in the angle data that justified
the trade changed enough to matter? Recommend hold, flag-for-attention, or
suggest-exit — never places or cancels an order itself.

## Why this one doesn't fit the plain trigger shape

Every other team so far is invoked because a person is in a conversation
asking for something. `trade_monitor` needs to run *whether or not anyone
is chatting* — a position can stay open for hours or days. Modeling that
as one long `delegate_to_team` call would mean a single tool call blocking
for the entire life of the trade, which the orchestrator's `AgentLoop`
was never built for and shouldn't be stretched to do.

**The actual fix isn't a new kind of always-on agent — it's reframing
each check as its own short, bounded run**, invoked by something outside
the user's conversation:

- An external scheduler (doesn't exist yet — a simple poller is enough,
  nothing fancy) wakes up every N minutes per open position and
  constructs `TeamManager` directly, calling `.run("check position for
  <symbol>")` — exactly the pattern already proven for real in
  `scratchpad/test_screener_team.py`, which built and ran a `TeamManager`
  with zero orchestrator involvement.
- Each invocation is a normal, bounded team run: fetch fresh angle data
  (reuse `get_all_angles`), compare against what justified the position
  originally (the strategy spec that authorized it), decide hold / flag /
  suggest-exit, write the result to `team_runs` like any other run.
- No new concurrency model, no background thread inside vinu-agent — see
  [00-overview.md](00-overview.md)'s "not out of the box" section for why
  this reframing avoids needing one.

## Scope & responsibilities

- **In scope**: one open position at a time; fresh angle read; compare
  against the original strategy spec's stated entry rationale (needs
  `strategist`'s spec to travel with the position — same `artifact_id`
  -style link `pnl_attribution`'s design doc already relies on for closed
  trades, reused here for open ones); a hold/flag/suggest-exit
  recommendation with reasoning.
- **Explicitly not in scope**: placing, modifying, or cancelling any real
  order — this team only ever recommends; whatever executes trades
  (outside vinu-agent, "Phase 6" in the existing project terminology)
  decides whether to act on the recommendation. Keeping the boundary hard
  here matters more than for any other team in this list — this is the
  one team touching a position that's already live with real money, and
  the architecture doc already flags real order-execution tooling as
  deliberately out of reach for specialists today.

## The real dependency this team is blocked on

Needs a `get_open_position_status`-style tool: current price, unrealized
P&L, time held, and the link back to the original strategy spec — same
missing "real position data" gap `risk_gatekeeper` is blocked on. These
two teams likely want the same underlying tool.

## How it adopts to vinu-agent, out of the box

Manager + specialist(s), `TEAM.md`/`AGENT.md`, but constructed and run by
an external scheduler via `TeamManager` directly rather than
`delegate_to_team` — see the trigger discussion above. Mechanism-wise,
zero new vinu-agent code beyond the missing tool; the new *external*
component (the scheduler) lives outside `vinu_agent` entirely.

## Position in the DAG

Runs continuously (in short, repeated bursts) while a position from
`risk_gatekeeper` is open, until the position closes and `post_trade_
review` takes over. See [00-overview.md](00-overview.md).

## Open questions

- Poll interval — fixed, or adaptive (check more often right after entry
  or near a stop)? Not decided.
- What happens with a `suggest-exit` recommendation if no one's watching —
  does it just sit in `team_runs` until someone checks, or does it need a
  push notification path? Not decided; depends on whatever the broader
  alerting story ends up being, out of scope for this doc.
