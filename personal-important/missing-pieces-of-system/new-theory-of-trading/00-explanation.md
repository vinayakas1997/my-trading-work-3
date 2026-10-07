# New theory of trading: must-conditions + supporting-indicator evidence (meta-labeling)

## Status: design-only, not yet built

Nothing described in this doc exists in the codebase today. Confirmed by
direct grep + read across `vinu-live`, `vinu-research`, and
`vinu-initial-analysis` (see "What already exists and why it's not this"
below) — this is new work, not a wiring problem like some other folders
in `missing-pieces-of-system/`.

## How we got here (the actual problem that started this)

The starting question was about live execution: could the system hold
several candidate trade plans "in the air" at once, watching conditions,
executing whichever one resolves first? Checking `vinu-live`'s real
orchestrator (`trade_plan/orchestrator.py`) showed that isn't how it
works at all — it only ever receives plans already marked `ACTIVE` from
`vinu-research` and either enters or manages an open position. No
concept of multiple watched candidates.

That led to a narrower, more concrete version of the same instinct:
take a real strategy — SMA(5) crosses above SMA(50) — and suppose the
cross fires but a filter (e.g. a risk score) hasn't confirmed yet. Should
the setup be dropped outright, or given a bounded grace window (e.g. the
next 10 candles) to confirm before being abandoned? Checking
`condition_evaluator.py` confirmed the current system evaluates every
rule as a stateless `metric operator threshold` triple, re-derived from
scratch every cycle — no memory across candles, no concept of "almost
passed," no grace period. A fail is a fail forever, until a brand new
trigger occurs.

That surfaced the real design question underneath: **not every failed
condition deserves the same treatment.** ADX sitting at 18 (below a
threshold of 20, but rising) is not the same kind of "fail" as ADX
sitting at 8 and falling. The first is a near-miss with visible
momentum toward passing; the second is a structural fail. Treating both
identically (as todays's system does) throws away real information.

Pulling on that thread further: if some conditions are allowed to be
"soft" (graded, not just true/false, and given time to resolve), then
the natural next step is to stop guessing which conditions should gate
entry at all, and instead **record everything, gate on nothing except
the true structural trigger, and let historical outcomes tell you which
recorded conditions actually mattered.** That's the idea this doc
describes. It is a known, well-established technique in systematic
trading called **meta-labeling** (primary model decides *whether an
opportunity exists*; a secondary layer decides *how much to trust it*),
applied here to this codebase's own vocabulary of strategies, angles,
and trade plans.

## The core idea in one sentence

Separate "does a trade opportunity exist" (a small number of hard,
structural trigger conditions) from "how much should I trust/size this
particular instance of it" (a larger, open-ended set of supporting
indicators recorded — never gated on — at the moment of the trigger,
whose historical relationship to outcomes is measured empirically over
time).

## The layers

### Layer 1 — Must-conditions (the primary trigger)

The small set of hard, structural conditions that define whether a
trade idea exists at all. Kept deliberately simple and few — this layer
should stay high-recall, not clever. If these don't all hold
simultaneously, there is no setup, full stop; no grace period applies
here (a cross either happened or it didn't).

**Example**: SMA(5) crosses above SMA(50).

A strategy can have more than one must-condition (e.g. "SMA5 crosses
above SMA50" AND "price is above the 200-day SMA" as a higher-timeframe
trend filter) — but every must-condition in this layer is a hard AND,
no exceptions, no scoring.

### Layer 2 — Supporting indicators (the evidence layer)

A basket of auxiliary indicators attached to the strategy that are
**not used to gate entry at all.** Some can be predefined by whoever
designs the strategy (ADX, volume-vs-average, a volatility regime
score, RSI, spread, time-of-day, whatever is plausible). Others don't
need to be known in advance — the strategy can simply say "log
whatever supporting signals are available" and let Layer 4 discover
which ones actually separate winners from losers. This matters: hand
picking which indicators "should" matter is exactly the kind of bias
this design is trying to avoid.

**Example supporting indicators for the SMA-cross strategy**:
- ADX(14) value at the moment of the cross
- Volume relative to its 20-day average at the moment of the cross
- A risk/shock score (already computed elsewhere in the system, e.g.
  `vinu-initial-analysis`'s shock/personality angles) at the moment of
  the cross
- Distance of price from the 200-day SMA (trend context)

None of these block the trade. They are just written down.

### Layer 3 — Shadow evaluation (snapshot + wait)

Every time a must-condition fires, take a full snapshot of every
supporting indicator's value at that exact instant, and record it
against a unique id for that trigger event. Then wait for the trade's
natural resolution horizon (however far forward the strategy's holding
period looks) and record the actual realized outcome — return, R
multiple, win/loss — against that same trigger id.

This is a pairing operation: **feature vector in, outcome label out**,
for every single trigger event the strategy has ever fired, going back
through historical backtests as well as forward through live/paper
trading.

**Example row this layer produces**:

| trigger_id | symbol | trigger_time | ADX | vol_vs_avg20 | risk_score | dist_from_sma200 | forward_return |
|---|---|---|---|---|---|---|---|
| t-00417 | AAPL | 2025-03-11 14:30 | 17.8 | 1.35 | 42 | +3.1% | +2.4% |
| t-00418 | MSFT | 2025-03-12 09:45 | 9.2 | 0.80 | 61 | -0.4% | -1.1% |

### Layer 4 — The probabilistic table (what the evidence is worth)

Once enough trigger events have accumulated (hundreds, not a handful),
bucket the rows by supporting-indicator state and look at the outcome
distribution per bucket. This turns vague intuition ("volume confirms
the trade") into a measured number: *when ADX is 15-20 and volume is
above 1.2x average, this setup has historically won 62% of the time at
1.4R average; when ADX is under 10, it wins 41% of the time at 0.6R.*

This is also where a supporting indicator earns or loses its keep. If
slicing the outcome table by a given indicator produces no meaningful
separation between buckets, that indicator isn't worth tracking further
for this strategy — the data says so, nobody had to guess up front.

This layer is also the natural home for answering the earlier "how many
candles should the grace window be" question: run the confirmation
window length itself as a swept parameter (the codebase already has a
generic sweep+walk-forward+PBO engine for exactly this kind of
question, see `vinu-research/vinu_research/sweep_grid.py`) and let the
same evidence process show which window length holds up out of sample,
rather than picking "10" by feel.

### Layer 5 — Risk management from experience (live use)

In live trading, when a must-condition fires, look up which bucket
today's supporting-indicator snapshot falls into, using the table Layer
4 built. That bucket's historical win-rate/expectancy becomes the
confidence signal driving:
- **Position size** — high-confidence bucket, larger size; low-confidence
  bucket, smaller size or skip entirely.
- **The grace-window decision from the earlier discussion** — a
  near-miss condition (e.g. ADX close to threshold, trending toward it)
  gets a grace window whose length and tolerance are themselves values
  looked up from Layer 4's evidence for that indicator, not a fixed
  global constant.
- **Stop/target placement** — a low-confidence bucket might warrant a
  tighter stop or smaller profit target than a high-confidence one, even
  though the must-condition (the entry trigger) is identical in both
  cases.

This is the payoff of the whole design: the "experience" the system
accumulates from every past trigger event — win or lose — becomes a
live, quantified input to how the *next* instance of the same setup is
sized and managed, instead of every occurrence of "SMA5 crossed SMA50"
being treated identically regardless of the context it happened in.

### Layer 5 extension — continuous position management, not just entry sizing

Everything in Layer 5 above describes a single lookup: snapshot
supporting indicators once, at the trigger, size the entry accordingly.
But Layer 3's snapshot doesn't have to stop at the trigger — it can keep
re-sampling the same supporting indicators every candle for as long as
the position stays open, and every re-sample can be looked up against
the same Layer 4 bucket table again. That turns entry sizing into
continuous, evidence-driven position management:

**Scaling in on improving conditions.** Entered small because the
supporting-indicator snapshot at trigger landed in a lower-confidence
bucket (e.g. ADX only 12, below strong confirmation). If continuous
re-sampling later shows ADX climbing into the historically stronger
bucket (15-20, the one the evidence table showed winning 62% of the time
at 1.4R), that's a real, evidence-backed reason to add to the position —
not because price moved favorably, but because the trade has been
re-classified into a bucket already known to perform better. This is
standard **pyramiding on confirmation**: size up only on new evidence,
never on price action alone.

**Scaling out on deteriorating conditions.** Entered full size because
conditions were strong at trigger. If continuous re-sampling later shows
the supporting indicators sliding into a worse bucket (risk_score
climbing, volume drying up), that's a reason to trim — proportionally,
not necessarily an all-or-nothing exit. If the current bucket's
historical expectancy is, say, 60% of what it was in the entry bucket,
reduce exposure by a comparable fraction rather than picking an
arbitrary trim size.

**What this needs that entry-only sizing doesn't:**
- Layer 3 becomes a *running* snapshot process (re-evaluate supporting
  indicators every candle while a position is open), not a one-shot
  snapshot at trigger time.
- A sizing function that maps a bucket-to-bucket transition (e.g.
  "moved from bucket B to bucket A") to an add/trim fraction. This
  function itself should be derived from historical evidence rather than
  hand-picked — the same historical trigger events used to build Layer
  4's outcome table can also be walked forward candle-by-candle to
  measure what a bucket transition at various points in a trade's life
  actually implied for the remaining forward return, which is what
  would justify a specific add/trim ratio instead of an arbitrary one.
- A clear separation from the must-conditions' own exit logic
  (invalidation / stop-loss) — this continuous re-sizing adjusts *how
  much* is on, it does not override the hard structural reasons a trade
  gets closed entirely.

## Worked example, start to finish

1. Strategy defines one must-condition: SMA(5) crosses above SMA(50).
2. Strategy also lists supporting indicators to always snapshot: ADX(14),
   volume-vs-avg20, risk_score, dist_from_sma200.
3. On 2025-03-11 14:30, AAPL's SMA5 crosses SMA50. Layer 3 snapshots:
   ADX=17.8, vol_vs_avg20=1.35, risk_score=42, dist_from_sma200=+3.1%.
   No entry decision is made from these values — they're just recorded.
4. 20 trading days later, the trade (had it been taken with a fixed
   exit rule) would have returned +2.4%. That number is written back
   against the same trigger id.
5. Repeat steps 3-4 for every historical AAPL/MSFT/... SMA cross across
   the backtest window, plus every one observed live going forward —
   hundreds of rows accumulate.
6. Layer 4 slices those rows: crosses with ADX 15-20 and vol_vs_avg20
   > 1.2 win 62% of the time at 1.4R; crosses with ADX < 10 win 41% at
   0.6R. `dist_from_sma200` turns out to show no separation at all —
   it's dropped from consideration for this strategy, not because
   anyone assumed it wouldn't matter, but because the data showed it
   didn't.
7. Live, on 2025-09-24, AAPL's SMA5 crosses SMA50 again with ADX=17,
   vol_vs_avg20=1.4. The system looks this up against the Layer 4 table,
   finds it falls in the high-confidence bucket, and sizes the trade
   larger than it would size a low-ADX occurrence of the same cross.

## What already exists and why it's not this

Checked before writing this doc, so this isn't duplicated work:

- `vinu_research.judgment_store.JudgmentStore` — calibrates the
  *research LLM's own approve/reject judgment quality* across
  iterations, not indicator states at a trade signal.
- `CalibrationTracker` / `_record_calibration_outcome`
  (`vinu-live/vinu_live/feedback_loop.py`) — tracks whole-strategy /
  whole-forecast accuracy (Brier score, directional correctness) over
  time. Aggregate, not conditioned on per-trigger supporting-indicator
  values.
- `HypothesisRegistry` / `_record_hypothesis_evidence`
  (`vinu-research/vinu_research/hypothesis_registry.py`) — each
  `Hypothesis` has a static `indicators_used` list and an `evidence`
  list of realized-return entries, but no indicator *value at trigger
  time* is recorded per evidence row, and there's no per-bucket outcome
  table.
- `shock_personality` / `shock_clustering`
  (`vinu-initial-analysis/vinu_initial_analysis/angles/`) — per-**symbol**
  behavioral regime stats (gap-fill rate, drift persistence), unrelated
  to any specific strategy's trigger event.
- `ShadowEvaluator` (`vinu-live/vinu_live/shadow_evaluator.py`) —
  gates whole-strategy BENCHING→ACTIVE promotion via paper P&L vs.
  backtest expectations. Not per-trade, not indicator-conditioned.

None of the above snapshot supporting-indicator values at the instant a
primary trigger fires and build an indicator-state-conditioned
forward-outcome table. That specific mechanism — Layers 3 and 4 above —
would be new storage and new logic, sitting between `vinu-strategy`
(which would own the must-conditions and the list of supporting
indicators to snapshot) and a new evidence store in `vinu-research`
(distinct in shape from `HypothesisRegistry`, since it needs one row
per trigger event with a full feature vector, not one row per
qualitative evidence note).

## Open questions for the next doc in this folder

- Where does the must-condition / supporting-indicator split get
  declared — as part of the strategy's own definition (in
  `vinu-strategy`), or as a separate config the research layer attaches
  after the fact?
- What does the new evidence store's schema look like, and does it
  live in `vinu-research` (alongside `HypothesisRegistry`) or as its
  own service?
- How is "bucket" defined in Layer 4 — fixed bins per indicator, a
  decision tree, or a simple nearest-neighbor lookup against historical
  rows? This determines how much data is needed before the table is
  trustworthy at all.
- How does this interact with `sweep_grid.py`'s existing PBO/
  walk-forward machinery, so the buckets themselves don't become
  overfit artifacts of the same historical window they were built from?
- For the continuous position-management extension: how often should
  the running re-snapshot happen (every candle vs. some coarser
  interval), and how is the bucket-transition-to-add/trim-fraction
  function actually estimated without needing an unrealistic amount of
  historical data (a trigger event supplies one entry-time row, but many
  in-trade rows over its holding period)?
