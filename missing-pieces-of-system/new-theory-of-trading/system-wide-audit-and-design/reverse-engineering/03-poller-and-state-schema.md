# Points 2 + 4 designed: the candle-close poller and the stage/state tracker

**Status: design-only, nothing built.** Covers the first two points from
`01-live-decision-loop-open-points.md`, in the order recommended when
this folder's plan was discussed: these two are the foundation everything
else (the live detector, the deciding agent) hangs off, so they get
designed first and in detail.

## Why these two are designed together

The poller (point 2) is what *drives* the state tracker (point 4) — every
time it detects a candle closed for a (ticker, strategy) pair, it's the
state tracker that gets evaluated next. They're two tables and one loop,
not two independent systems.

## Part A — the candle-close poller (point 2)

### The core design choice: data-based watermark, not time-based cron

Two ways to detect "a candle just closed": (a) compute candle boundaries
deterministically from the timeframe and fire on a clock (e.g. every 15
minutes at :00/:15/:30/:45), or (b) track the latest bar actually seen
per (ticker, timeframe) and fire when a newer one appears.

**Chosen: (b), the watermark approach.** A pure clock-based fire would
misfire across weekends, holidays, and vendor delivery delays — exactly
the kind of gap `../02-open-questions-strategy-and-simulation.md` item
#15 already found nothing in this codebase currently detects
automatically. A watermark, compared against the real latest bar, only
fires when a bar has actually, genuinely arrived — the same "trust the
real data, not the clock" posture as that item's `days_stale` proposal.

### Schema: `live_poll_cursor`

One row per (ticker, timeframe) — not per (ticker, strategy), since
multiple strategies can share the same ticker+timeframe and should share
one fetch, one cursor, not duplicate the work:

```
live_poll_cursor:
  ticker: str
  timeframe: str              # e.g. "15m", matches StrategyConfig.schedule's own value
  last_processed_bar_ts: timestamp   # the most recent bar_ts this cursor has already fired for
  updated_at: timestamp
  PRIMARY KEY (ticker, timeframe)
```

### The loop

Same `while True: cycle(); sleep(interval)` shape already used by every
other worker in this stack (confirmed pattern across `vinu-live`'s
`scheduler.py`, `feedback_loop.py`, `shadow_evaluator.py`, per the parent
audit's own repeated citations of this convention):

1. Build the distinct set of (ticker, timeframe) pairs currently needed,
   from every active strategy's `StrategyConfig.schedule` (point 1 — no
   new data needed, reuse the existing field).
2. For each pair, fetch the latest bar (one fetch shared across every
   strategy watching that ticker+timeframe, not one fetch per strategy —
   avoids the exact "no caching, re-fetch per caller" pattern the parent
   audit already flagged three separate times, items #11.4, #13.4, #21).
3. Compare the fetched bar's `bar_ts` against `live_poll_cursor`'s stored
   `last_processed_bar_ts` for that pair.
4. If newer: for every strategy registered against this (ticker,
   timeframe), emit a candle-close event carrying `{ticker, strategy_id,
   timeframe, bar_ts, bar_data}` — this is the input to Part B below.
   Then advance `last_processed_bar_ts` to the new `bar_ts`.
5. If not newer: do nothing for this pair this cycle.

**Poll interval**: needs to be meaningfully shorter than the shortest
timeframe any active strategy uses (e.g. if the shortest is 15m, poll
every 60s, mirroring `vinu-live`'s existing worker-interval convention),
so a candle close is detected promptly rather than up to one full
timeframe late. A guessed starting constant, same posture as
`FORWARD_HORIZON_BARS`/`floor_multiple` elsewhere in this design series —
meant to be tuned once this is actually running, not treated as final.

**Open, not decided here**: which service owns this loop — see point 8
in `01-live-decision-loop-open-points.md`, deliberately left for its own
discussion rather than folded into this schema pass.

## Part B — the stage/state tracker (point 4)

### The states

Five stages, replacing today's fully stateless evaluation (confirmed
stateless — no memory across candles — per `../../00-explanation.md`'s
citation of `condition_evaluator.py`):

```
idle
  -> a must-condition has not fired; nothing pending for this
     (ticker, strategy) right now.

fired_awaiting_confirmation
  -> a must-condition fired, but the strategy has soft/near-miss
     conditions that get a grace window before being treated as
     confirmed or abandoned (the original grace-window idea from
     ../../00-explanation.md's "how we got here" section).

ready_to_execute
  -> must-condition(s) fired AND any grace-window confirmation
     succeeded (or the strategy has no soft conditions at all, in
     which case this is reached directly from idle). This is the
     hand-off point to point 5's agent.

executed
  -> the agent (point 5) acted on this trigger. Terminal for this
     specific trigger_id.

expired
  -> the grace window elapsed without confirmation. Terminal for this
     specific trigger_id.
```

After `executed` or `expired`, the tracker resets to `idle` (trigger_id
cleared) to watch for the *next* occurrence of the must-condition — these
are terminal only for one trigger's lifecycle, not permanently for the
(ticker, strategy) pair. A must-condition can fire again later; "a cross
either happened or it didn't" (per `00-explanation.md`'s Layer 1
description) applies fresh each time.

### Schema: `strategy_stage_state` (current state, one row per pair)

```
strategy_stage_state:
  ticker: str
  strategy_id: str
  stage: enum(idle, fired_awaiting_confirmation, ready_to_execute, executed, expired)
  trigger_id: str | null        # set once a must-condition fires; links to point 3's
                                 # live-detector output row for this trigger event
  entered_stage_at: timestamp
  grace_window_expires_at: timestamp | null   # only set during fired_awaiting_confirmation
  last_checked_bar_ts: timestamp   # ties to live_poll_cursor's bar_ts that drove this check
  updated_at: timestamp
  PRIMARY KEY (ticker, strategy_id)
```

### Schema: `strategy_stage_transitions` (append-only history)

Current-state tables alone would silently lose the trail — the same
mistake Decision 1 already warns against ("do not pre-bucket, pre-
threshold, or pre-decide anything... record everything, raw") and the
same shape as item #21.3's `RejectionRecord` idea (record *why*, don't
just overwrite). Every transition gets its own row, never overwritten:

```
strategy_stage_transitions:
  id: auto
  ticker: str
  strategy_id: str
  from_stage: enum | null    # null for the very first transition
  to_stage: enum
  trigger_id: str | null
  bar_ts: timestamp          # the candle-close event (Part A) that caused this transition
  reason: str                 # e.g. "must_condition_fired", "grace_window_confirmed",
                               # "grace_window_expired", "agent_executed"
  created_at: timestamp
```

### The evaluation logic, per candle-close event from Part A

Given `{ticker, strategy_id, timeframe, bar_ts, bar_data}`:

1. Load the current `strategy_stage_state` row for (ticker, strategy_id)
   (create one at `idle` if this pair has never been seen before).
2. **If `idle`**: check must-condition(s) against `bar_data` (needs
   point 3's live indicator computation to evaluate the condition's
   inputs). If fired: has soft/grace conditions? → transition to
   `fired_awaiting_confirmation`, set `grace_window_expires_at` (a
   guessed constant window length, same posture as everywhere else in
   this series — a real value belongs to point 9's evidence table once
   it exists, not picked here). No soft conditions? → transition
   straight to `ready_to_execute`. Either way, a trigger_id gets
   generated here and handed to point 3 to snapshot indicators against.
3. **If `fired_awaiting_confirmation`**: check confirmation condition(s)
   against `bar_data`. Confirmed → `ready_to_execute`. Grace window
   elapsed (`bar_ts > grace_window_expires_at`) without confirmation →
   `expired`. Neither yet → stay, no transition row written (only real
   transitions get logged, not "still waiting" no-ops).
4. **If `ready_to_execute`**: this pair is waiting on point 5's agent to
   act. The poller does not re-evaluate must-conditions again here —
   avoids a second must-condition firing while the first is still
   awaiting a decision, which would corrupt `trigger_id` attribution.
5. **If `executed`/`expired`**: reset to `idle`, clear `trigger_id`, so
   the next must-condition firing starts a clean cycle.

Every actual transition (not every candle-close check) writes one row to
`strategy_stage_transitions` — a "stayed the same" evaluation produces no
new row, keeping the history table meaningful rather than one row per
candle regardless of whether anything happened.

## What this deliberately leaves open

- The exact must-condition/confirmation-condition evaluation engine this
  logic calls into — `../02-open-questions-strategy-and-simulation.md`
  item #2 already flags `vinu-strategy/engine/rules.py`/`rules_engine.py`
  as a possible existing engine to reuse here rather than building a new
  one; not decided in this pass.
- The grace-window length as a real, evidence-derived value (currently a
  guessed constant) — depends on point 9's bucket table existing.
- How point 5's agent actually gets notified that a row reached
  `ready_to_execute` (a poll of its own, or a direct call from step 3/
  step 5 above) — left for point 5's own design pass.
