# Project vision: a system that grows its own confidence

## The core idea

There is no real trading history yet. No capital has actually been risked,
so every threshold, every calibration weight, every "this trade scored
well" judgment in the system today is either a hand-picked default or a
backtest-derived estimate — not something proven against real, live
outcomes.

The instinct that could come from that gap is to wait until there's real
data before building anything adaptive. The vision here is the opposite:
**build the system so it already knows it doesn't know yet, behaves
accordingly — cautious, theory-driven, prepared for a wide range of
situations rather than confident about one — and then grows stronger, on
its own, exactly in step with how much real evidence it has actually
earned.** Not a system that's either "off" (no real trading, so nothing
adaptive runs) or "on" (pretends day-1 confidence is the same as
day-500 confidence) — a system with a real, continuous growth curve
between those two states, and agents that read where on that curve the
system currently is before deciding how much to trust their own numbers.

## Why this isn't a new idea for this codebase — it's the existing pattern, generalized

This system already refuses to trust a number until it has earned trust,
in several independent places:

- `vinu-research/vinu_research/decay.py` — `compute_decay_metrics`,
  `evaluate_health`: a strategy's health evaluation is gated on having
  enough real trade history before it's allowed to downgrade/upgrade a
  strategy's status. Propose → approve, never a silent leap.
- `vinu-research/vinu_research/trade_score_calibration.py` —
  `record_trade_score_outcome`, `compute_calibration_metrics`,
  `propose_calibrated_thresholds`: TradeScore's own sub-weights only
  nudge toward what real outcomes suggest once a minimum sample size is
  met, bounded per step, never a hard jump.
- `vinu-agent/vinu_agent/broker/performance_store.py` — the Shadow
  promotion gate's `min_paper_days≥5` check: an artifact isn't trusted
  with real capital until it has survived a minimum stretch of
  paper-trading first.
- `vinu-research/vinu_research/calibration.py` — `CalibrationGate`:
  forecast accuracy (Brier score, directional correctness) must clear a
  sample-size bar before it's allowed to gate anything.

Every one of these is the same shape: **don't trust a number until enough
real evidence exists to back it, and even then, nudge, don't leap.** What's
missing is not the pattern — it's that each of these currently computes
its own local, private notion of "do I have enough evidence yet," with no
shared, system-wide answer to "how mature is this system, right now,
overall." An agent reasoning about a brand-new ticker in a brand-new
market regime has no way to know it should be *more* cautious than usual,
because "usual" caution is baked into fixed per-mechanism defaults, not
adjusted by how much the system as a whole currently knows.

## The growth model, restated simply

- **No real trades yet** → lean hard on theory: backtests, simulated
  scenarios, wide safety margins, conservative position sizing, more
  "what could go wrong in each of these situations" than "here's the
  number." Risk less, not because the opportunity is smaller, but because
  the system's own confidence in its numbers is smaller.
- **A little real history accumulates** → the system's calibration
  mechanisms (already built, see above) start producing real signal, but
  only in the narrow slice of conditions actually observed so far — the
  system should know it's only proven itself in that slice, not
  everywhere.
- **Real history broadens** (more tickers, more regimes, more time) → the
  system leans progressively more on live-observed calibration and
  progressively less on theoretical priors, tier by tier, with the shift
  itself gated the same sample-size-and-bounded-nudge way every existing
  calibration mechanism already works.
- **Mature** → the system's own agents are, in effect, trading on a track
  record they've actually built, not one they were configured to assume.

This is deliberately not framed as "turn a switch from paper to live" —
it's a continuous maturity signal every calibration point in the system
can read and adjust its own behavior against, the same way a human trader
naturally trades smaller and more theoretically until their own track
record on a given setup earns them the right to trade it with more
conviction.

## Where the detailed design lives

The concrete design for the piece that makes this real — what computes
the system's current maturity, where it sits relative to the database and
the agent teams, and how many agents (if any) are actually involved — is
in a separate, implementation-focused doc so this vision file stays about
*why*, not *how*:

**`missing-pieces-of-system/maturity-agentic-system/`**

That folder is where the maturity-tier signal, its inputs, its outputs,
and exactly which existing agents consult it get worked out in full
detail.

## Relationship to the narrating agent vision

This isn't a separate initiative from the narrating-agent idea already
written up in `missing-pieces-of-system/narating-agents/` — it's the
missing ingredient that vision needs to actually be safe to build. A
narrating agent that decides how much capital to risk and how
aggressively to trade a ticker needs to know, as one of its own inputs,
how much the *system itself* currently knows versus how much it's still
guessing — that's exactly what the maturity signal is for. The narrator
consumes it; it doesn't replace it.
