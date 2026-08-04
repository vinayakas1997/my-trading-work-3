---
name: knowledge-library-entities
status: definition-phase
purpose: the full set of "entities" that make up the agent's knowledge-library world, thought through independent of which vinu-* component owns each one — deliberately done in this order (entities first, component-mapping second) so the mapping doesn't silently collapse into "whatever vinu-agent already does." Companion to 01-vinu-questions-prompt.md (the daily ritual questions) — this file is what those questions actually draw on.
---

# The Knowledge-Library — What Entities the Agent's World Is Made Of

## Why this file exists, and why entities-first

`01-vinu-questions-prompt.md` defined the 8 questions a session must
answer. Answering them well requires the agent to draw on a real body of
knowledge — but before deciding which `vinu-*` component should own each
piece of that knowledge, it's worth naming what the pieces actually are.
Jumping straight to "which file in `vinu_agent`" collapses the answer into
whatever the codebase already happens to do, the same trap flagged
elsewhere in this project's docs. This list is deliberately written before
that mapping exercise.

## 1. Self-state — truth about the agent's own book

- Cash, positions, cost basis, live P&L, exposure by symbol/sector
- Order history and live order status (working, filled, rejected)
- Margin/buying power, account-level constraints

## 2. Live market reality

- Real-time price/quote (bid/ask, last trade), timestamped
- Historical OHLCV (context for indicators, not just today's number)
- Options chain / greeks / IV where relevant
- Corporate actions — splits, dividends, upcoming earnings dates
- Market calendar — open/closed, holidays, session type

## 3. News & information flow

- Live/real-time news feed
- Historical news archive (a ticker's narrative arc, not just today)
- Macro/economic calendar (Fed meetings, CPI prints, earnings season) —
  regime-moving events not tied to a single ticker

## 4. Derived analytics — `vinu-initial-analysis`'s actual output

- significance_score, novelty_score, peer_relative_strength
- regime_features (vol regime, trend regime)
- Cross-asset/peer correlation structure
- **Critically: what each of these is *proven* to predict vs. not** (the
  signal-usage-contract gap) — this has to travel with the signal, not
  live separately from it

## 5. Research/backtest knowledge — the "what's been tested" library

- `vinu-simulator`'s Monte Carlo / strategy backtests, promotion metrics
  (Sharpe/CAGR bar)
- `vinu-research`'s statistical validation results
- The 1-month agentic replay itself (this project's own case study — "here's
  what actually happened when this agent ran for real")
- **Permanent, hard-won facts that must never be silently re-forgotten** —
  e.g. "direction prediction from sentiment doesn't work, tested twice,
  ~50% coin-flip." This is knowledge *about* the knowledge, and it's
  exactly the kind of fact a future agent could otherwise "rediscover" is
  untrue and quietly start relying on again.

## 6. Strategy & decision knowledge

- Generated trade plans (entry/exit/invalidation rules)
- The structured decision journal itself (thesis, invalidation level,
  status, predicted vs. actual) — **implemented** since this file was
  first written: `01-plan-and-implementations/03-structured-decision-
  journal.md` reused `vinu-research`'s existing `HypothesisRegistry`
  rather than building new storage; `trade_plan_tool.py` now writes each
  generated plan into it, surfaced back every session via item 2's
  ground-truth block. Predicted-vs-actual on position close is not yet
  confirmed built — verify before assuming this entity is fully closed.
- Risk mandate / risk-budget tiers — the governor's current state, not
  just its existence

## 7. Simulation / what-if knowledge

- Monte Carlo paths, tail-risk/stress scenarios — "if this position moves
  against me by X, what happens"
- Distinct from #5: #5 is "what was tested historically," this is "what
  could plausibly happen from here"

## 8. Live-trading-specific awareness

- Real broker state (paper vs. live flag — must never be ambiguous)
- Execution quality — realized slippage vs. what was modeled/expected

## 9. Meta-knowledge — the agent's own audit trail and known limitations

- The audit log itself (item 4 from `03-on-agent-consiuness/01-plan-and-
  implementations/`) — what actions were taken, when, why
- **This project's own known-bug history** (tool-call dropout, frozen
  mark-to-market, the fabrication incident) — should a future agent
  instance know these are documented, previously-seen failure modes of
  *itself*, the same way #5's "direction doesn't work" fact has to
  persist? This is a genuinely new category — self-awareness of one's own
  documented failure modes, not just market knowledge.

## 10. External benchmark/context knowledge

- Peer/sector/index performance, VIX, rates, dollar index — the wider
  regime context a single-ticker view can't provide on its own

## 11. Human/operator context

- Risk tolerance and constraints as actually configured (not assumed)
- Escalation path — who/what to defer to when confidence is genuinely low
  (still the unsolved piece project-wide, but it needs somewhere in this
  map to attach to)

## What's most novel here, worth not losing

Categories 5 and 9 aren't named explicitly anywhere in `03-on-agent-
consiuness/01-quant-agent-qualities.md`. They're the new insight from doing
this exercise: **the agent needs to know things about its own track record
and its own documented weaknesses, not just about the market.** A knowledge
library that only covers market/portfolio state and skips "what has already
been proven not to work" and "what has this specific agent already been
caught doing wrong" would silently let both mistakes recur.

## Next step — not done in this file

Map each of the 11 categories above to the actual `vinu-*` component(s)
that should own/produce it (`vinu-initial-analysis`, `vinu-simulator`,
`vinu-research`, `vinu-agent`, or none yet). Deliberately not done here —
this file's job was the entity list; the mapping is the next piece of work.

## Related documents

- [`01-vinu-questions-prompt.md`](01-vinu-questions-prompt.md) — the daily
  ritual questions this knowledge library feeds.
- [`../03-on-agent-consiuness/00-start-here.md`](../03-on-agent-consiuness/00-start-here.md)
  — full context chain for why this line of work exists at all.
- [`../03-on-agent-consiuness/01-plan-and-implementations/AGENTS.md`](../03-on-agent-consiuness/01-plan-and-implementations/AGENTS.md)
  — the four mechanisms already planned that several of these entities feed
  into (items 1-4).
