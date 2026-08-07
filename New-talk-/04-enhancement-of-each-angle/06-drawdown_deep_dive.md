---
name: angle-06-drawdown_deep_dive
status: decided
purpose: discussion and enhancement proposal for the `drawdown_deep_dive` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/drawdown_deep_dive/`.
---

# 06 — drawdown_deep_dive

**Title (from spec.yaml):** Drawdown Deep-Dive

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `drawdown.py` / `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/drawdown_deep_dive/`
- Not a forecaster — an event detector + attribution tool. Different
  shape of angle than ARIMA/Chronos/DLinear.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

This angle finds every time a stock's price fell hard from a recent high
and later climbed back, measures exactly how fast the fall and the
recovery each were, and checks whether news was around when it happened —
so we can later ask questions like "do sharp drops happen more in a
certain session or day of the week."

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Drawdown threshold | -2% | kept as-is from the real code (`drop_threshold_pct = -2.0` in `compute.py`) |
| Timeframes | 15min, 1H, 1D | kept as-is from the real `spec.yaml` — narrower than ARIMA's 6, judged intentional for this kind of analysis |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca (price), shared news pipeline (same source already feeding `news` into every angle's `compute()`) | no new news source invented |
| Scope | **every** detected drawdown, not just the single worst one | current code only analyzes the worst drawdown per run — this angle needs the full set to build a meaningful per-time-slice profile |
| Duration unit | candle count, not real time | consistent with the earlier ARIMA/N-candle decision — makes 15min/1H/1D comparable |
| Lifecycle fields (new) | `peak_ts`, `peak_price`, `trough_ts`, `trough_price`, `recovery_ts`, `recovery_price`, `duration_to_trough` (candles), `duration_to_recovery` (candles) | fixes the real gap: the current code never records a recovery timestamp at all, despite the title promising "duration, recovery time" |
| Speed metrics (new) | `trough_speed` = `drop_pct / duration_to_trough`; `recovery_speed` = `recovery_gain_pct / duration_to_recovery` | both in %-per-candle — shows how fast a move was, not just how big |
| Shape checkpoints (new) | 25% / 50% / 75% progress markers (candle count) within both the formation phase (peak→trough) and the recovery phase (trough→recovery) | reveals whether a move was a sudden capitulation/V-shaped bounce vs. a slow bleed/grind — real information the original code has zero visibility into |
| Checkpoint crossing rule | first candle that reaches that % threshold | simplest rule, consistent with how peak/trough are already detected in the existing code |
| Unrecovered drawdowns | kept in the dataset, marked `status: open` / not yet recovered, recovery-phase fields left null | a drawdown still open at the end of the date range is meaningful information on its own, not something to silently drop |
| News tracking | split into `formation_news` (peak→trough) and `recovery_news` (trough→recovery), each a tagged list of articles — no single blended attribution percentage | replaces the current unvalidated `news_driven_pct` heuristic with honest counts/presence instead of a fabricated confidence number |
| `lookback_hours` field | removed | dead code in the current implementation — computed but never used downstream |
| Time-based tagging | drawdown episode tagged by its `peak_ts`, using session/day-of-week/week/month/quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| Purpose of tagging here | likelihood/probability tracking, not a definitive causal conclusion | explicitly not claiming certainty — same thin-sample caution as other angles, `n` always carried alongside any per-slice stat |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |

## 4) Example — what one result looks like

**One full drawdown episode (recovered case):**

```
symbol: AAPL
timeframe: 1D
status: recovered

peak_ts: 2024-05-10T13:30:00Z
peak_price: 148.50
trough_ts: 2024-05-16T13:30:00Z
trough_price: 142.30
drop_pct: -4.17
duration_to_trough: 6
trough_speed: -0.70   # % per candle

formation_checkpoints:
  25%: candle 1  (price 146.90)
  50%: candle 2  (price 145.30)
  75%: candle 4  (price 143.60)

formation_news:
  - {ts: 2024-05-14T09:00:00Z, headline: "AAPL misses Q2 estimates", sentiment: BEARISH}

recovery_ts: 2024-05-30T13:30:00Z
recovery_price: 148.80
recovery_gain_pct: 4.57
duration_to_recovery: 14
recovery_speed: 0.33   # % per candle

recovery_checkpoints:
  25%: candle 3
  50%: candle 7
  75%: candle 12

recovery_news:
  - {ts: 2024-05-28T14:00:00Z, headline: "AAPL announces buyback", sentiment: BULLISH}
```

**After tagging** (per [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md), applied to `peak_ts`):

```
+ session: ny
+ subsession: markethours
+ day_of_week: Friday
+ week_of_month: 2
+ month: May
+ quarter: Q2
```

**After aggregation (queryable key):**

```
NY-MARKETHOURS-1330-2000-1D = 0.8 drawdowns/month, avg duration_to_trough 5.2 candles,
  avg duration_to_recovery 11.4 candles, news present in formation 62% of cases (n=38)
```

**Unrecovered case (kept, not dropped):**

```
symbol: TSLA
timeframe: 1D
status: open
peak_ts: 2026-06-01T13:30:00Z
peak_price: 210.00
trough_ts: 2026-06-20T13:30:00Z
trough_price: 189.40
drop_pct: -9.81
duration_to_trough: 13
recovery_ts: null
recovery_price: null
duration_to_recovery: null
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per detected drawdown episode
  (not just the worst), carrying every field shown in §4, tagged by
  `peak_ts`. Same "never overwritten, source of truth" principle as
  every other angle.
- **Layer 2 — precomputed common keys**: session + subsession +
  timeframe combinations precomputed after each run — drawdown
  frequency, avg speed, avg duration, news-presence rate — each
  carrying `n` (number of drawdown episodes in that bucket).
- **Layer 3 — on-demand query service**: same shared service as every
  other angle, composes any custom slice combination from Layer 1 on
  demand.

No new storage architecture needed — this angle reuses the same 3-layer
design and metadata conventions as ARIMA/Chronos/DLinear; the only
difference is a richer per-row schema (lifecycle fields, speed metrics,
shape checkpoints, two news lists) instead of a forecast + hit field.

## 6) What we will achieve / how to use it

- A real drawdown lifecycle profile per time-slice: how often drawdowns
  happen, how fast they fall, how fast they recover, and whether news
  tends to be present — replacing the original code's single
  worst-drawdown-only, unvalidated-percentage output.
- Shape information (25/50/75% checkpoints) that reveals *how* a drop or
  recovery unfolds — sudden capitulation vs. slow bleed, V-shaped bounce
  vs. grind — not just its size.
- An honest, non-fabricated view of news involvement: real counts and
  timestamps of what news existed during formation vs. recovery, instead
  of a confidence-sounding percentage that was never actually validated.
- Framed explicitly as likelihood/probability information for
  understanding drawdown behavior over time, not as a definitive causal
  claim about what "caused" any individual drawdown.

## 7) Deeper rationale

**Why analyze every drawdown, not just the worst one:** a per-time-slice
profile (frequency, avg duration, news-presence rate) is meaningless
built from a single worst-case data point per run — it needs the full
population of drawdown episodes to say anything statistically real about
"when do drawdowns tend to happen."

**Why candle-count duration instead of real time:** identical reasoning
to the earlier N=100 decision for ARIMA — keeps comparisons fair across
15min/1H/1D, since a fixed real-time window means wildly different candle
counts per timeframe.

**Why drop the original attribution percentage formula:** the existing
`news_driven_pct` calculation (`weighted_score / (weighted_score +
0.1*n_events + 1.0)`, capped at 95%) has no empirical grounding — its
constants were chosen to "look reasonable," not derived or validated
against real outcomes. Presenting it as a precise-looking percentage
risks implying more certainty than actually exists. Honest counts and
timestamps of nearby news, split by formation vs. recovery phase, give
the same underlying information without a fabricated confidence number.

**Why keep unrecovered drawdowns instead of dropping them:** silently
excluding drawdowns that haven't recovered by the end of the date range
would bias every duration/recovery-speed statistic toward only the
"nice" cases that happened to resolve in time — a real distortion, since
slower or more severe drawdowns are exactly the ones most likely to still
be open at a cutoff date.

**Why the shape checkpoints (25/50/75%) matter:** two drawdowns with an
identical `drop_pct` and `duration_to_trough` can have completely
different characters — one could be a single violent drop, another a
steady grind down. The checkpoints capture that difference, which the
original code (peak/trough endpoints only) has no way to express.

**Why "likelihood," not "conclusion":** with a -2% threshold over ~4.5
years, drawdown events are inherently less frequent than every-candle
forecasts (ARIMA/Chronos/DLinear), so some time-slice combinations will
have small `n`. Framing outputs as probability/likelihood, always paired
with `n`, keeps the tool honest about its own statistical confidence
rather than presenting thin-sample results as settled fact.

**What "-2%" is measured from, and how trending stocks are handled:**
the threshold is not measured from a fixed reference point — it's
measured from the most recent **rolling peak** (the code keeps updating
"peak" to the newest high whenever not already in a drawdown). This means:
- **Uptrending stocks**: handled correctly and naturally — the peak keeps
  climbing with the trend, so every ≥2% pullback from the latest high
  still gets detected as its own episode.
- **Persistently downtrending stocks**: the real edge case. A drawdown
  only closes once price makes a new high *above the original peak* (full
  recovery) — so a multi-year decline that never regains its old high
  produces **one single, continuously-deepening drawdown episode**, not a
  series of separate "legs down." Choppy bounces along the way don't
  reset anything unless they exceed the original peak. This is exactly
  why keeping unrecovered drawdowns (`status: open`, see above) matters —
  without that, a stock in a long structural decline would either never
  appear in the dataset or would silently vanish once the date range
  cuts off. The shape checkpoints still capture whether that long decline
  was smooth or choppy internally, even though it's one long episode
  rather than several.

**Open/unresolved:** no external research paper is being cited for this
angle's design — the lifecycle/shape/news-window approach here is a
custom design decided in this conversation, not sourced from a published
method, so no citation applies the way it did for DLinear or Chronos.

## FUTURE-PERSONAL-PROJECT

Not part of the current design — a personal idea flagged during this
discussion (2026-08-07), to revisit later, separate from this angle's
build scope:

Once this angle produces a rich, tagged dataset of drawdown episodes
(lifecycle timing, speed, shape checkpoints, and paired formation/
recovery news), that dataset itself becomes solid **training data** for
a purpose-built model — not necessarily a full LLM, more likely a small
classifier/regressor — trained to predict things like "given current
conditions plus recent news, how likely/severe/fast is a drawdown right
now."

Known tradeoff to revisit when this comes up again: with a -2% threshold,
drawdown events are relatively rare (see the thin-sample caution in §3/§7
above), so enough historical episodes need to accumulate across enough
tickers before there's a real training set — this is a "come back to once
the dataset is built up" idea, not something to start on now.
