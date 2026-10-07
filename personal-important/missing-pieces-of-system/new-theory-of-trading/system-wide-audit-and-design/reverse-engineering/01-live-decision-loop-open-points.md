# The 9 points: what vinu-live needs to reach the end goal

**End goal, stated once, precisely**: before acting on a trade, `vinu-
live` checks (1) the strategy's precondition is true right now, and (2)
what the 29th angle's recorded evidence says has historically happened
the last N times this exact condition fired — and decides using both.
See `00-overview.md` for where this end goal comes from.

Each point below: what it is, whether it already exists, and what real
gap (if any) it points at, cited against the parent audit series where
one already exists.

## 1. Strategy → ticker → polling cadence

Each strategy needs to declare how often/on what timeframe it should be
checked (e.g. "every 15-minute candle"). **Already exists**:
`StrategyConfig.schedule`, per `../03-strategy-definition-full-schema.md`'s
description of the real, current schema. Reuse as-is, nothing new
needed here.

## 2. The candle-close poller

Something that fires, per (ticker, strategy), the instant that
strategy's own timeframe's candle closes — not a fixed-interval sweep of
the whole portfolio. **Does not exist today.** `vinu-live`'s current
`LiveScheduler` polls on a fixed interval across the whole portfolio at
once (per the parent audit's item #24 trace of `scheduler.py`), not
per-ticker, per-strategy-timeframe, event-driven on candle-close. New
mechanism needed.

## 3. Live indicator computation — the "live detector"

The same kind of point-in-time indicator snapshot `signal_evidence`
(angle #29) computes for historical backfill, but computed live, the
instant a new candle closes, instead of walked over historical bars.
**Confirmed missing** — `../../how-to-use-29th-angle/01-track1-how-it-
works-today.md`'s own last line: "The LIVE detector... does not exist."
Also named in the parent audit as item #5's `live_snapshots` idea
(`../02-open-questions-strategy-and-simulation.md`) — same shape as
backfill's indicator snapshot, but keyed on real wall-clock time instead
of a historical date range.

## 4. A stage/state tracker per (ticker, strategy) — not stateless

Today's condition evaluation has **no memory across candles** — a fail
is a fail forever until a brand-new trigger occurs, with no concept of
"almost passed" (confirmed directly against `condition_evaluator.py` in
`../../00-explanation.md`'s "how we got here" section). The end goal
needs real state: `must_condition_not_fired` →
`fired_awaiting_confirmation` (a grace window, per `00-explanation.md`'s
original grace-window discussion) → `ready_to_execute` →
`executed`/`expired`. **Does not exist** — this is the concrete
mechanism the "what stage is it at" idea needs underneath it.

## 5. The agent that reads that state and decides

This is `../../00-explanation.md`'s **Layer 5** ("Risk management from
experience, live use") — explicitly one of the layers not yet built.
It's the piece that, once a must-condition fires (or is in its grace
window), calls `get_signal_evidence`/`get_move_evidence` to check what's
historically happened, and turns that into an actual decision — size,
grace-window length, or skip. **Does not exist.**

## 6. Precondition `defined`/`tested` tracking

`../03-strategy-definition-full-schema.md` item 4 already proposes a
`defined`/`tested` split on a strategy's precondition — whether a
precondition has actually been checked against real evidence yet, not
just asserted. Point 4 (the stage tracker) and this are the same idea
from two angles: the agent in point 5, at the moment it actually acts,
is exactly what should flip `tested: false → true`. **Schema proposed,
nothing wired.**

## 7. The agent's decision has to survive contact with execution

Even once this agent decides "act," it hands off into a `vinu-live`
execution path that the parent audit's **item #24** already found has
two still-open CRITICAL gaps: `LiveScheduler.cycle()` never calls
`check_limits()` (no risk-limit check on the main path at all), and
`SignalTranslator.translate()` doesn't net same-symbol orders from
different strategies (a real buy-then-sell whipsaw is possible). A
carefully evidence-informed decision from point 5 can still get executed
unsafely, or collide with another strategy's opposite order on the same
symbol, if these aren't fixed. **Confirmed still open, not new here** —
this point is about the connection, not a new gap.

## 8. Where this new poller/agent architecturally lives

Not decided anywhere. `vinu-initial-analysis` is backfill-rhythm
(triggered by ticker discovery, runs over historical date ranges) — the
wrong home for something that needs to be live-rhythm (per candle-close,
real-time). `../01-planning.md` Decision 10 already flags this
distinction ("the still-unbuilt LIVE detector `vinu-live` would need for
real-time execution decisions... a separate concern with a different
rhythm") and names `vinu-live` as the natural home, but nothing there has
actually been designed. **Open architectural decision, not yet made.**

## 9. Layer 4's probabilistic/bucket table doesn't exist yet either

Today, "asking the 29th angle" only returns raw historical counts — no
computed win-rate or confidence number — because Phase 3/Layer 4 (the
analysis/bucketing layer) isn't built (confirmed in both
`../../how-to-use-29th-angle/01-track1-how-it-works-today.md` and
`05-track2-how-to-ask.md`'s own honesty sections: "never a computed win
rate or statistic"). The agent in point 5 can still work off raw
evidence in the meantime, but the actual "how much should I trust this"
number `00-explanation.md`'s Layer 5 was designed around doesn't exist
yet. **Confirmed still open, not new here.**

## What's next

Ordering/dependency discussion (which of these 9 blocks which, and what
the actual build sequence should be) is a deliberate follow-up pass, not
done here — see `00-overview.md`'s "Status" section for why.
