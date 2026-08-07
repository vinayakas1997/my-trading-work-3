---
name: angle-02-backtesting_44_metrics
status: decided
purpose: discussion and enhancement proposal for the `backtesting_44_metrics` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/backtesting_44_metrics/`.
---

# 02 — backtesting_44_metrics

**Title (from spec.yaml):** Backtesting Metrics

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` / `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/backtesting_44_metrics/`
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

This angle is not a forecaster — it's a report card for a symbol's price
history: it looks at how the price moved over a period and summarizes that
into numbers like "how much did it gain," "how risky was the ride," and
"how often did it go up vs down."

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Real metric count | 18 | title/spec say "44+" but the actual `compute.py` computes 18 — documented as a known gap between name and reality, not silently fixed |
| Metric split | 11 "core" (time-sliceable) + `ann_vol` (context) + 6 whole-history-only | see breakdown below — matches how ARIMA's CI-coverage is the one number that gets tagged/sliced |
| Core (time-sliceable) metrics | `total_return`, `cagr`, `sharpe_ratio`, `sortino_ratio`, `calmar_ratio`, `max_drawdown`, `win_rate`, `avg_win`, `avg_loss`, `win_loss_ratio`, `profit_factor` | these answer "did it perform well / was it risky" — meaningful even on a smaller per-slice sample |
| Whole-history-only metrics | `var_95`, `var_99`, `cvar_95`, `tail_ratio`, `skewness`, `kurtosis` | tail-risk and distribution-shape stats need a large sample to mean anything — computed once over the full history, never tagged/sliced |
| Context metric | `ann_vol` | kept alongside the core group as supporting context (Sharpe/Sortino depend on it), not a primary time-sliced signal on its own |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1D, 1W, 1M, 6M (9 total) | union of ARIMA's 6 finer timeframes + this angle's existing 4 (1D/1W/1M/6M reused, not dropped) |
| Low-sample-size flag | 1M and 6M marked low-confidence / context-only | over ~4.5 years of data, 1M gives ~54 candles and 6M gives ~9 — too thin to draw real conclusions from, but still computed and shown with their `n` so the thinness is visible, not hidden |
| Date range | 2022-01-01 → 2026-Q2 | same range as ARIMA, for consistency across angles |
| Data source | Alpaca | same as ARIMA |
| Time-based tagging | session / day-of-week / week / month / quarter, applied to the 11 core metrics only | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) — not re-decided here |

## 4) Example — what one result looks like

**Whole-history-only metrics (computed once, never sliced):**

```
symbol: AAPL
date_range: 2022-01-01 to 2026-06-30
var_95: -0.021
var_99: -0.038
cvar_95: -0.029
tail_ratio: 0.87
skewness: -0.42
kurtosis: 3.1
```

**Core metric, single tagged row (from the 1D timeframe, before aggregation):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
sharpe_ratio: 1.34
win_rate: 0.58
max_drawdown: -0.062
```

**After tagging** (per [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)):

```
+ session: ny
+ subsession: markethours
+ day_of_week: Wednesday
+ week_of_month: 3
+ month: May
+ quarter: Q2
```

**After aggregation (queryable key):**

```
NY-MARKETHOURS-1330-2000-1D = sharpe_ratio 1.28, win_rate 61% (n=912)
NY-MARKETHOURS-1330-2000-6M = sharpe_ratio 0.95, win_rate 55% (n=9, low-sample-size flag)
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: every core-metric computation, one row per
  step per timeframe, tagged the same way as any other angle (see §4).
  Whole-history-only metrics are stored separately, one row per symbol per
  date-range run — they are never tagged or sliced.
- **Layer 2 — precomputed common keys**: same as ARIMA — session +
  subsession + timeframe combinations precomputed after each run, each
  carrying `n`.
- **Layer 3 — on-demand query service**: same shared service as ARIMA —
  builds any custom key combination from Layer 1 at query time.

Reuses the exact same 3-layer architecture and metadata conventions
already defined for ARIMA — no new storage design needed here, this angle
just plugs its own metrics into the same machinery.

Every stored/precomputed/queried result carries: `symbol, timeframe, N
(sample count for that slice), date_range, metric_name, metric_value,
run_timestamp`. Results computed once per run and cached, same as ARIMA —
not recomputed on every use.

## 6) What we will achieve / how to use it

- A real answer to "when does this symbol actually perform well" — e.g.
  spotting that a symbol has a much better Sharpe ratio during NY market
  hours than pre-market, or that Wednesdays have a systematically higher
  win rate.
- A risk picture that isn't just one flat number for the whole history —
  drawdown and win-rate broken down by session/day/week shows *when* the
  risk actually shows up, not just that it exists somewhere.
- Whole-history tail-risk/distribution numbers (VaR, CVaR, skew, kurtosis)
  stay as an honest "big picture" risk summary, uncorrupted by being
  sliced into samples too thin to trust.
- Same as ARIMA, this reuses the shared tagging/storage design, so once
  built it costs nothing extra to plug in the next angle that wants
  time-sliced results.

## 7) Deeper rationale

**Why split into core vs whole-history-only instead of tagging everything:**
tail-risk metrics (VaR, CVaR, tail ratio) and distribution-shape metrics
(skewness, kurtosis) are, by definition, about rare/extreme events or the
overall shape of a large sample. Slicing them into something like "AAPL,
Wednesday, NY session" leaves too few data points for the number to mean
anything — the same thin-bucket problem already flagged in the common
tagging doc. The core group (returns, risk-adjusted ratios, drawdown,
win/loss) stays meaningful even on smaller per-slice samples, so only
those get tagged.

**Why the real metric count (18) is documented instead of silently
"fixed" to match the "44+" title:** the spec/title overpromise relative to
the actual code. Rather than quietly padding the count or renaming the
angle, the gap is written down here as a known discrepancy — a decision
for later on whether to add the missing metrics or rename the angle, not
something to gloss over.

**Why keep 1M/6M despite being too thin to trust:** dropping them
outright removes information someone might still want to eyeball (e.g. "is
there even a rough trend here"). Keeping them but attaching `n` and a
low-sample-size flag is the same principle used everywhere else in this
design — never hide a thin sample, just make sure it's visible as thin.

**Why the same date range and data source as ARIMA:** consistency —
results from different angles become directly comparable (same window,
same source) instead of each angle silently using a slightly different
backtest period.

**Open/unresolved:** whether the 6 missing metrics (to close the gap from
18 to the claimed "44+") should actually be added is not decided here —
out of scope for this pass, flagged for a future discussion.
