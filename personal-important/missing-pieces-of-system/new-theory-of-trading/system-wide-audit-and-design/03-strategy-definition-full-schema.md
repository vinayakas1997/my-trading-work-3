# The full strategy definition schema — every field it should carry

**Status: design-only, nothing implemented.** This consolidates and
supersedes item #1's original "why" schema in
`02-open-questions-strategy-and-simulation.md`, expanded across several
rounds of discussion into the complete field set a strategy definition
needs. Written against the real current `StrategyConfig`
(`vinu-strategy/vinu_strategy/models/strategy.py`) and `Hypothesis`
(`vinu-research/vinu_research/models.py`) so every gap named below is a
real, checked gap, not a guess.

## Why a strategy definition needs more than conditions + a pipeline

Today's real `StrategyConfig` has `name`, `description`, `schedule`,
`features_required`, `correlation_required`, `angles_required`,
`pipeline` (`selection`/`allocation`/`timing`/`risk`), `universe`,
`metadata`. This is enough to *run* a strategy. It is not enough to
**falsify** one — to state, in a checkable way, what it's claiming, what
it expects to see, what would prove it wrong, and how it's actually
performed. Every field below exists to close one specific piece of that
gap, tied to something already discovered elsewhere in this folder.

## 1. The must-condition / supporting-indicator "why" (original item #1)

```
must_conditions: [
  { condition: "sma5_cross_sma50", why: "momentum initiation signal" }
]
supporting_indicators: [
  { indicator: "adx_14", why: "expected to filter false crosses in choppy regimes" }
]
```

Each "why" is a falsifiable claim, meant to be checked against Track 1's
recorded evidence (once wired in — see item #16.1 in
`02-open-questions-strategy-and-simulation.md`), not documentation for
humans to read and forget.

## 2. Link to the real hypothesis-tracking mechanism that already exists

```
hypothesis_id: "hyp_2026-09-25_aapl_sma_cross"
```

`HypothesisRegistry` (`vinu-research/hypothesis_registry.py`) already has
the lifecycle (`exploring`/`testing`/`validated`/`rejected`/`monitoring`/
`mc_gate_failed`), the evidence list, and the invalidation-reason field
this whole design was trying to build fresh — see item #1's update in
`02-open-questions-strategy-and-simulation.md`. Right now hypotheses get
matched to strategies via a fragile fuzzy text comparison
(`loop.py`'s `_match_score`, 0.5 threshold — item #16.4). An explicit
`hypothesis_id` field removes that fragility entirely: no guessing, no
false merges, no missed matches.

## 3. Risk management — stated explicitly, not left to the pipeline's generic `risk` stage

```
risk_management: {
  stop_loss: { method: "atr_multiple", value: 1.5 },   # exit if adverse move exceeds 1.5x ATR(14)
  take_profit: { method: "atr_multiple", value: 3.0 },  # target 2:1 reward:risk
  max_risk_per_trade_pct: 1.0,                          # of allocated capital
  sizing_profile: {                                      # which CompositeSizer factors apply (item #14)
    vol_target: true,
    evidence_confidence: true,
    regime_aware: false,
    correlation_aware: true
  }
}
```

Today's `pipeline.risk` stage (`PipelineStage` in `strategy.py`) only
knows `method: normalize | none` — a portfolio-level weight-normalization
step, not a per-trade risk definition. This is a different, missing
layer: what specifically invalidates *this one trade*, and which sizing
factors (item #14's composite sizer) this strategy expects applied to
it. Without `sizing_profile` stated explicitly, a backtest and live
trading could silently apply different, inconsistent sizing to what's
supposed to be "the same" strategy.

## 4. Precondition and postcondition — Track 2's PRE/POST structure, applied to strategy design

This is the direct parallel raised in discussion: Track 2 records what
the market looked like *before* a real move (PRE) and how it degrades
*after* the peak (POST) — see `../how-to-use-29th-angle/02-track2-design.md`. A strategy
definition should state the same two things as **claims to be checked**,
not just something Track 2 observes after the fact:

```
precondition: {
  description: "market should be quiet/ranging for at least 20 candles before the SMA cross",
  defined: true,
  tested: false     # has this actually been checked against recorded evidence yet, or is it still just an assumption?
},
postcondition: {
  description: "after entry, ADX should climb above 25 within 5 candles if the move is real",
  defined: true,
  tested: false
}
```

The `defined`/`tested` split matters on its own: a strategy can have a
fully written-out precondition that **sounds** rigorous while having
never actually been checked against a single real recorded trigger. This
field makes that distinction visible and queryable, instead of a
precondition silently sitting in the same limbo whether it's been
validated or not.

## 5. Failure definition — two distinct levels, not one blurred concept

Two genuinely different questions, both named explicitly "when does the
strategy fail" in discussion, and worth keeping separate:

```
failure_definition: {
  trade_level: {
    description: "exit if adverse move exceeds stop_loss, or if postcondition ADX check fails by candle 5",
    # this is the per-trade invalidation rule -- when does THIS ONE TRADE end in a loss
  },
  strategy_level: {
    description: "reject the whole hypothesis after 10 trades if win rate < 35% or expectancy < 0",
    triggers_reject_with_reason: true
    # this is when the STRATEGY ITSELF should be retired, not just one trade closed
    # -- feeds directly into HypothesisRegistry.reject_with_reason() (item #7)
  }
}
```

Conflating these two would be a mistake: a strategy can lose a trade
completely normally (that's what a stop-loss is for) while the strategy
itself remains valid; the strategy-level failure definition is what
should actually trigger `reject_with_reason()`'s lifecycle transition,
not every individual losing trade.

## 6. The performance record — a reference, not inline data

The record of everything the strategy has actually done should **not**
be duplicated inline in the definition — it already exists, split across
real stores, and the definition should just point at it:

```
performance_record: {
  hypothesis_id: "hyp_2026-09-25_aapl_sma_cross",   # -> HypothesisRegistry.evidence[]
  signal_evidence_trigger_ids: [...],                # -> Track 1's SignalEvidenceStore rows (once #16.1 is wired)
  move_evidence_move_ids: [...],                     # -> Track 2's MoveEvidenceStore rows, if this strategy's
                                                      #    entries correspond to detected big moves
  sweep_run_ids: [...]                               # -> vinu-simulator's simulation_runs, via item #3/#14's
                                                      #    sweep-grouping table once it exists
}
```

The point of this being a **reference list**, not copied data: the
definition stays small and current, while the full trail — every trigger,
every move, every backtest run — stays queryable from its actual source
of truth, with no duplication to keep in sync.

## 7. Origin and versioning

```
origin: { source: "agent" | "human", generation_run_id: "...", candidate_slot: 2 },
schema_version: "1.0"   # bumped when the STATED HYPOTHESIS changes, distinct from policy_version
                         # (which tracks angle-config changes) -- feeds HypothesisRegistry's
                         # updated_at/invalidation_reason lifecycle (item #7) with something precise
                         # to track evolution against, not a silent overwrite
```

`origin.generation_run_id`/`candidate_slot` ties back to item #16.2 —
once generation-time candidates are actually recorded instead of
discarded, this is how a strategy definition traces back to exactly
which LLM draft produced it, enabling the "do agent-written strategies
validate better than human ones" question to actually be answerable
later.

## 8. Regime and confound context

```
expected_regime: ["bull", "neutral"],   # item #6 -- a stated, checkable claim, not a vague intuition
news_sensitivity: "exclude"             # "exclude" | "include" | "target" -- item #9's news-confound flag,
                                         # stated per-strategy since different strategies want opposite answers
```

## What this schema deliberately does NOT try to solve

This is a field list, not a storage design — where each of these fields
actually lives (a new section of `StrategyConfig` itself vs. a separate
linked file vs. rows in `HypothesisRegistry`) is not decided here, same
as item #1 originally left open. Nor does this decide *when* `tested`
flips from false to true, or what statistical bar `strategy_level`
failure requires — those depend on Phase 3 (Track 1's analysis layer)
existing, which it doesn't yet.

## Nothing here has been implemented

Recorded as a complete design reference, per instruction — every field
is a proposal to discuss and decide on, not a schema already in use
anywhere in the codebase.
