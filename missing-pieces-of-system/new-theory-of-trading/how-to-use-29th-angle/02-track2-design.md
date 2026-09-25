# Track 2: strategy-agnostic big-move recording — full design

**Status: design settled across this conversation, nothing implemented
yet.** This file exists so the whole design is written down in one
place, in full, before any code gets touched.

## The core idea, precisely

Track 1 (see `01-track1-how-it-works-today.md`) always starts from a
condition ("SMA5 crossed SMA50") and asks "what happened after." Track 2
inverts that direction entirely: it starts from a real, already-happened
significant price move — detected from pure price action, no strategy
or must-condition involved at all — and records the full anatomy of that
move: what the market looked like *before* it started, *during* it, and
*as it degraded/reversed*. Confirmed directly by the user: "the pure
price movements when there is no strategy defined is correct."

The point of doing this: Track 2's recorded evidence (what reliably
precedes a real big move) becomes the research material that should
inform which must-condition Track 1 is even built around — turning
strategy design into something read off observed behavior, instead of
starting from one guessed example (SMA5×SMA50) indefinitely.

## Step 1 — detecting "a big move" (no condition, pure price action)

**Decided (2026-09-25, Decision 14 in `../01-planning.md`): ATR-multiple,
starting at 2×ATR(14)** — see `03-move-detection-threshold-options.md`
for the full trade-off writeup against the two alternatives considered
(return z-score, rolling percentile). It's relative to the ticker's own
volatility, not a flat percentage — a fixed number means something
different for a sleepy utility stock than for a volatile small-cap. 2× is
the deliberate starting multiplier; 2.5×/3× remain live comparison points
once real recorded moves exist.

## Step 2 — the three-phase recording structure (PRE / DURING / POST), refined into a checkpoint sequence

Agreed directly in this conversation as a structure that generalizes
beyond just Track 2 — it's also a real gap in Track 1's current schema
(which only captures a collapsed version of DURING). The three phases:

- **PRE** — the window of candles *before* the move started. Was it
  quiet, already trending, choppy, building volume? This is the
  "leading signature" nothing currently records at all.
- **DURING** — from move-start to the move's peak. How many candles to
  build, how smooth vs. spiky, volume profile, momentum shape.
- **POST / degrading** — from peak to when the move actually reversed or
  flattened. How it unwound, how sharp, how much it gave back.

Each phase has a **length in candles** (recorded, not fixed globally —
different moves take different numbers of candles in each phase) and,
for each of the 52 already-implemented indicators (same set Track 1
uses — no need to reinvent), the **average value of that indicator
within that phase's window**.

**Refinement agreed 2026-09-25: DURING is not one blob — it's a sequence
of checkpoints.** Instead of only averaging indicators across the whole
DURING window, also snapshot all 52 indicators every time the move
crosses a new magnitude checkpoint relative to the 2×ATR floor (2×ATR →
2.5×ATR → 3×ATR → 3.5×ATR → ... for as far as the move actually goes, no
ceiling — see the "no ceiling" note in Step 4). Each checkpoint records:
- the ATR-multiple level reached (e.g. `2.5`)
- the full 52-indicator snapshot at that instant
- candles elapsed since the previous checkpoint
- **rate of change since the previous checkpoint**, per indicator (e.g.
  RSI rose 3 points over those candles vs. 0.5 points) — a level can
  look identical at two checkpoints while its trajectory says opposite
  things about what's coming next, so the level alone is not enough.
- a **volume-divergence flag**: true when price is still extending
  (moving to a new checkpoint) while `volume_vs_avg20` is *declining*
  compared to the previous checkpoint — the classic exhaustion tell,
  captured as an explicit derived flag rather than left for someone to
  eyeball later.

This makes the DURING phase a queryable sequence, not a single averaged
number, and directly strengthens Step 5's edge-finding (below): you can
now ask "what changed in the indicators right as the move pushed from
2× to 2.5×ATR, and again from 2.5× to 3×?" — showing which indicators
keep confirming as a move extends, versus which stop being useful past
a certain point.

## Step 3 — the request/API shape (the "wrapper feature class" contract)

Modeled directly on `SignalEvidenceStore`'s proven shape (same
storage-layer pattern, not a new architecture):

```
POST /research/move-evidence/record
{
  "move_id": "AAPL-up-2026-03-11T14:30",
  "symbol": "AAPL",
  "direction": "up" | "down",
  "outcome": "extended" | "failed",   # see "recording failures" below
  "start_time": "...",   # move begins (crossed 2xATR floor)
  "peak_time": "...",    # move's extreme point (null if outcome=failed and never re-extended)
  "end_time": "...",     # degrade phase concludes (reversed/flattened)
  "magnitude_pct": 3.2,               # start -> peak, the raw number, NO CEILING
  "magnitude_bin": "3.0-3.5%",        # see Step 4
  "duration_bin": "fast" | "medium" | "slow",   # see Step 4
  "duration_candles": {"pre": 30, "during": 14, "post": 6},
  "granularity": "15min",
  "session": "ny" | "london" | "tokyo" | "overlap" | "off_hours",
  "day_of_week": "tue",
  "relative_strength_vs_benchmark": 1.8,   # this ticker's move size / benchmark's move size over the same window -- idiosyncratic vs. market-wide
  "retest": {                              # post-move: did price come back to the breakout level?
    "occurred": true,
    "held": true,                          # true = retested and bounced, false = retested and failed through
    "candles_to_retest": 9
  },
  "indicators": {
    "pre":    {"adx": 14.2, "rsi": 48.1, "volume_vs_avg20": 0.9, ...},
    "during": {"adx": 27.6, "rsi": 71.4, "volume_vs_avg20": 1.8, ...},
    "post":   {"adx": 19.3, "rsi": 55.0, "volume_vs_avg20": 1.1, ...}
  },
  "checkpoints": [
    {
      "atr_multiple": 2.0,
      "time": "...",
      "candles_since_prev": 0,
      "indicators": {"adx": 22.1, "rsi": 61.0, "volume_vs_avg20": 1.4, ...},
      "rate_of_change_since_prev": {"adx": null, "rsi": null, ...},
      "volume_divergence": false
    },
    {
      "atr_multiple": 2.5,
      "time": "...",
      "candles_since_prev": 4,
      "indicators": {"adx": 26.8, "rsi": 68.3, "volume_vs_avg20": 1.1, ...},
      "rate_of_change_since_prev": {"adx": 4.7, "rsi": 7.3, ...},
      "volume_divergence": true
    }
  ],
  "policy_version": "..."
}
```

The `indicators` block (and each checkpoint's `indicators`) reuses the
exact same 52-indicator set Track 1 already computes — nothing new to
build there, just averaged over each phase's window (for `pre`/`during`/
`post`) or read at a single point-in-time bar (for each checkpoint).

### Recording failures, not just extensions

**Agreed 2026-09-25**: a move that touches the 2×ATR floor and then
immediately reverses *without* reaching 2.5×ATR is recorded too, tagged
`"outcome": "failed"`, with `magnitude_pct` capped at whatever it
actually reached and `checkpoints` containing just the single 2×ATR
entry. Without these negative examples, Step 5's "what differentiates a
real move" comparison only ever sees moves that worked — it has no way
to tell what a checkpoint looks like right before a move dies, only what
one looks like right before it kept going. Recording both is what turns
this into an actual comparison rather than a one-sided catalog.

## Step 4 — binning: magnitude AND duration, two independent dimensions

The user's original idea: bin by magnitude (2%, 2.5%, 3%, ...) and track
frequency per bin, plus attach session/day-of-week. Confirmed sound and
matches real, documented market-microstructure effects (session-driven
volatility, day-of-week seasonality are real, studied phenomena, not
invented). One addition made during this conversation: bin by
**duration/speed** too, as a second, independent dimension — a 3% move
in 5 candles and a 3% move over 200 candles are fundamentally different
things, and a single magnitude bin would otherwise conflate them. So two
independent binnings: magnitude bin × duration bin (e.g. fast/medium/
slow), not just one.

**No ceiling, confirmed 2026-09-25**: 2×ATR is a floor to qualify as
"big" at all, never an upper cap. A move that runs to 7×ATR or beyond is
recorded with its real `magnitude_pct` and binned wherever it actually
lands — nothing is thrown away for being "too big," consistent with
Decision 1's "record raw, bucket later" rule.

## Step 5 — finding "the edge": which indicators actually differentiate

The user's proposed methodology: compare each indicator's average across
the three phases (pre vs. during vs. post). An indicator that stays
nearly identical across all three phases is telling you nothing useful
for this purpose; an indicator that shifts clearly and consistently is a
real signal worth paying attention to — "our edge."

**Confirmed sound, with one refinement made during this conversation**:
compare using a **normalized difference** (an effect size, e.g.
`(during_avg - pre_avg) / pre_std`), not the raw average gap. Different
indicators live on completely different scales (RSI 0-100, ADX 0-100 but
behaving differently, `volume_vs_avg20` centered around 1.0) — a raw gap
of "5" means something different for each one. Normalizing puts every
one of the 52 indicators on the same comparable footing, so they can
genuinely be ranked against each other by "how much did this one
actually move around a real big move," rather than large-scale
indicators dominating the comparison by accident of units.

**Extended 2026-09-25 to use the checkpoint sequence and the failures.**
The same normalized-effect-size comparison applies checkpoint-to-
checkpoint (2×→2.5×, 2.5×→3×, ...), not just phase-to-phase — this shows
*where along a move's life* each indicator stops being useful (e.g. an
indicator might differentiate strongly at the 2×→2.5× step but say
nothing by 4×→4.5×, meaning it's an early-confirmation signal, not a
late one). And because failed moves (see Step 3) are recorded with the
same shape, the comparison can also be run **extended vs. failed at the
same checkpoint level** (e.g. "at 2×ATR, what did the indicators look
like for moves that went on to 3× vs. moves that died right there?") —
this is the actual edge-finding query, not just pre/during/post.

## How this differs from Phase 3 (Track 1's still-unbuilt analysis layer)

Track 2's "summary on demand" capability (a `get_move_summary(symbol)`-
style read, mirroring the already-working `get_signal_evidence` tool
pattern from Track 1) is **simpler than Phase 3** and doesn't need to
wait for it: it's descriptive statistics over recorded moves ("this
ticker has had 14 big moves in the last year, typically building over 8
candles, degrading over 5, usually preceded by a volume pickup 3-4
candles earlier"), not the deep quantile-bucketed win-rate/expectancy
analysis Phase 3 is meant to eventually provide for Track 1. This is
intentionally a lighter, separate capability that can be built and used
before Phase 3 exists.

## Two more fields, agreed 2026-09-25: relative-move context and retest behavior

- **Relative-move context** (`relative_strength_vs_benchmark` in the API
  contract above): one extra field comparing this ticker's move size to
  a benchmark's (index or sector ETF) move size over the same window.
  Turns "was this idiosyncratic to this ticker, or did the whole
  market/sector move together" into a queryable dimension instead of a
  guess — cheap to compute (one more ratio), no new indicator
  infrastructure needed.
- **Retest behavior** (`retest` block in the API contract above): after
  POST, does price come back to test the breakout level, and hold or
  fail through it? A natural, cheap extension of the already-agreed POST
  phase that tells you whether a move was structurally real or just a
  spike.

## What's still genuinely open before any code gets written

1. ~~The move-detection threshold itself~~ — decided: 2×ATR(14), see
   `03-move-detection-threshold-options.md`. The final multiplier value
   (2× vs. 2.5× vs. 3×) is still open pending real data.
2. Exact PRE/DURING/POST window lengths — fixed candle counts, or
   dynamically detected (e.g. PRE = however far back until the price
   was "quiet" by some definition)? Not discussed yet in this
   conversation.
3. Where this lives architecturally — a new angle (like `signal_evidence`
   itself), or a different mechanism entirely, given it has no
   must-condition to hang off of the same way Track 1's angle does.
4. Storage location — a new table/store, or an extension of
   `SignalEvidenceStore`? Given the schema is genuinely different (one
   row per move with three indicator-average sub-blocks, vs. Track 1's
   one-row-per-trigger-plus-child-table shape), a separate store seems
   more consistent with Decision 8's own reasoning (right-sized storage
   per genuinely different data shape), but this hasn't been decided.
