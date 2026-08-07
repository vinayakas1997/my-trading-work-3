---
name: angle-03-chronos
status: decided
purpose: discussion and enhancement proposal for the `chronos` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/chronos/`.
---

# 03 — chronos

**Title (from spec.yaml):** Chronos Time-Series Foundation Model

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` / `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/chronos/`
- Currently genuinely `pretrained` — real foundation-model weights are downloaded
  and loaded at run time (`amazon/chronos-t5-tiny` in the deployed code), not a
  fallback. The code does have a `fallback_proxy` path for when weights/network
  are unavailable, but since weights are confirmed present and loaded, this
  backtest design does not need to account for fallback results mixing in.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

Chronos is a ready-made AI model (built and pretrained once by Amazon, not
trained on our own data) that reads the last several hundred candles and
predicts the next 5, giving three lines instead of one — a most-likely
guess, a pessimistic guess, and an optimistic guess.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Context length (N) | 512 candles | Amazon's own stated ceiling for this model family — also adopted as our fixed requirement, not a growing/adaptive window like ARIMA's N=100 |
| Model checkpoint | `chronos-t5-large` (710M params) | upgraded from the code's current default (`chronos-t5-tiny`, 8M params) — see full size table in §7; the smaller checkpoints were not silently kept, the full trade-off is written down below |
| Forecast horizon | 5 steps ahead | fixed output shape of this model, unlike ARIMA's 1-step |
| Uncertainty band | p10 / median / p90 (80% interval) | not directly comparable to ARIMA's 95% CI — labeled explicitly as an 80% band, not forced to look like ARIMA's number |
| Hit definition | actual candle value falls inside that step's p10-p90 band | checked independently per horizon step (1 through 5) |
| Model backend | always `pretrained` | fallback_proxy path exists in code but is out of scope here since real weights are confirmed loaded |
| Backtest method | walk-forward (rolling predict + check + slide) | same method as ARIMA |
| Storage shape | one row per walk-forward evaluation, with a nested `predictions` dict keyed by horizon step (1-5), each holding p10/median/p90/actual/hit | avoids repeating the same session/day/week tags 5 times per evaluation — see §4 |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | same 6 as ARIMA |
| Date range | 2022-01-01 → 2026-Q2 | same as ARIMA |
| Data source | Alpaca | same as ARIMA |
| Baseline comparison | naive random-walk (forecast = last close), same backtest | same rationale as ARIMA — check Chronos is actually adding value |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as ARIMA |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |

## 4) Example — what one result looks like

**One walk-forward evaluation (one row, nested predictions):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
session: ny
subsession: markethours
day_of_week: Wednesday
week_of_month: 3
month: May
quarter: Q2
model_backend: pretrained
checkpoint: chronos-t5-large
predictions: {
  1: {p10: 141.0, median: 142.3, p90: 143.8, actual: 142.8, hit: true},
  2: {p10: 140.2, median: 142.6, p90: 144.5, actual: 143.1, hit: true},
  3: {p10: 139.5, median: 142.9, p90: 145.3, actual: 145.9, hit: false},
  4: {p10: 138.9, median: 143.2, p90: 146.0, actual: 144.0, hit: true},
  5: {p10: 138.1, median: 143.5, p90: 146.8, actual: 141.2, hit: false}
}
```

**After aggregation (queryable key, per horizon step):**

```
NY-MARKETHOURS-1330-2000-1D-STEP1 = 86% (n=912)
NY-MARKETHOURS-1330-2000-1D-STEP5 = 61% (n=912)
```

(Deliberately shows accuracy decaying by horizon step — that decay is itself
one of the useful conclusions this backtest produces, see §6.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per walk-forward evaluation, tags
  applied once per row (not per horizon step), predictions nested as a dict
  keyed 1-5 as shown in §4.
- **Layer 2 — precomputed common keys**: session + subsession + timeframe +
  horizon_step combinations precomputed after each run, each carrying `n`.
- **Layer 3 — on-demand query service**: same shared service as ARIMA,
  reads Layer 1, unpacks the nested `predictions` dict to answer any custom
  key combination (including specific horizon steps) not already in Layer 2.

Reuses the same 3-layer architecture and metadata conventions defined for
ARIMA — the only addition is that Layer 3's query logic needs to unpack the
nested `predictions` field, since this angle's raw rows aren't flat.

Every stored/precomputed/queried result carries: `symbol, timeframe, N=512,
date_range, checkpoint, horizon_step, hit_rate, n_forecasts, run_timestamp`.
Results computed once per run and cached, same as ARIMA.

## 6) What we will achieve / how to use it

- A real, measured answer to "does Chronos's zero-shot forecast actually
  hold up on real price data," per timeframe and per how-far-ahead it's
  predicting — not just trusting the model's own confidence.
- Visibility into **accuracy decay by horizon step** — seeing whether step-1
  predictions are meaningfully better than step-5 tells us how far ahead
  this model can actually be trusted, which matters for how it gets used
  downstream.
- A direct, apples-to-apples comparison against ARIMA's step-1 result and
  against the naive baseline — since both use the same date range, symbols,
  and tagging, "does a full AI foundation model actually beat a simple
  statistical formula on this data" becomes an answerable question, not a
  guess.
- Confirms whether the spec's own caveat ("general TSFMs tend to
  underperform finance-specific models") holds up on our real data, or not.

## 7) Deeper rationale

**Why 512 as a fixed requirement, not a growing window like ARIMA's N=100:**
Amazon's own model card states 512 as both the default and maximum context
length for this Chronos family — it isn't a "recommended minimum" the way
30-100 observations is for ARIMA, it's a hard architectural ceiling. Since
the ceiling is fixed and well below what's typically available once the
backtest is running, we simply require the full 512 before evaluating,
rather than mixing a growing-window design onto a model that always
truncates to its last 512 candles anyway. Amazon does **not** publish an
official minimum — so unlike the ceiling, the earlier floor decision (100,
matching ARIMA) is our own choice, not something to misattribute to Amazon.

**Model checkpoint sizes — the full trade-off, not hidden:**

| Model | Parameters |
|---|---|
| chronos-t5-tiny | 8M |
| chronos-t5-mini | 20M |
| chronos-t5-small | 46M |
| chronos-t5-base | 200M |
| chronos-t5-large (chosen) | 710M |

Source: [amazon/chronos-t5-tiny](https://huggingface.co/amazon/chronos-t5-tiny),
[amazon/chronos-t5-small](https://huggingface.co/amazon/chronos-t5-small),
[amazon/chronos-t5-large](https://huggingface.co/amazon/chronos-t5-large)
on Hugging Face; context length (512, both default and max for this
family) confirmed via the same model cards.

The deployed code currently defaults to `tiny` (8M params) — almost
certainly picked for speed/low resource cost, not accuracy. That trade-off
is made explicit here rather than carried forward silently: `large`
(710M params) is the decided choice for this backtest, prioritizing
forecast quality over speed. This will cost meaningfully more compute per
walk-forward step than `tiny` would — not yet benchmarked, same open
caveat as ARIMA's unbenchmarked refit-cost concern (see
[01-arima.md](01-arima.md) §7). **Future work**: the other sizes (mini,
small, base) remain worth trying later as a speed/accuracy trade-off study
once `large`'s real results and real cost are known — not committed to now,
just flagged as a real option for later.

**Why the p10-p90 band is reported as 80%, not treated as equivalent to
ARIMA's 95% CI:** forcing the two numbers to look comparable would be
misleading — they're measuring different confidence widths by construction.
Keeping the true 80% label intact, and only comparing step-1 hit-rate
directly, keeps the ARIMA-vs-Chronos comparison honest.

**Why check per-horizon-step instead of only step 1:** step-1-only would
under-use what Chronos actually outputs (a genuine 5-step forecast) and
would hide a potentially important finding — that accuracy may degrade
sharply after step 1 or 2. Checking all 5 steps, tagged by horizon_step,
answers both "is Chronos accurate" and "how far ahead is it still useful."

**Why nested predictions instead of 5 flat rows:** avoids duplicating the
same session/day/week/quarter tags 5 times per evaluation; keeps "one row =
one real model call" consistent with how ARIMA's raw rows work. The query
layer (Layer 3) absorbs the small extra complexity of unpacking a nested
field, rather than pushing duplication into every stored row.

**Open/unresolved:** actual compute cost of running `chronos-t5-large`
across a full walk-forward backtest (especially 1min/5min timeframes) has
not been benchmarked — same category of open caveat as ARIMA's refit-cost
concern, needs real measurement before committing to a refit cadence for
the finer timeframes.
