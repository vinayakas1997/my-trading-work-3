# 05 — drawdown_deep_dive

- **Angle id:** `drawdown_deep_dive`
- **Cluster:** C — Volatility & drawdown risk
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/drawdown_deep_dive/`
  (`compute.py` = live output, `drawdown.py` = detection logic, `backtest.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Finds every time this ticker fell at least 2% from a high before making
a new high, and reports how deep each fall was and the worst one. It is
backward-looking risk context, not a forecast. **Its news attribution
currently never finds any news** (see F1), so it cannot tell you why a
drawdown happened.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | A drawdown is "the maximum cumulative loss from a peak to a following bottom" of **one value series**. | [M1] |
| A2 | How deep drawdowns get depends on the **length of the window and the volatility** -- they are not comparable across different windows or different stocks without adjusting. | [M1] |
| A3 | A threshold that adapts to recent volatility (e.g. a multiple of ATR) separates meaningful drops from normal noise better than a fixed %. | code's own design (`detect_drawdown_episodes`), supported by A2 |
| A4 | ATR (Average True Range) measures typical bar-to-bar range, smoothed with Wilder's formula. | [W1] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Price follows a random walk, zero drift | Expected max drawdown = **1.2533 × σ × √T** -- grows with volatility and with the square root of time. | [M1] |
| R2 | Positive drift (profitable) vs. negative drift (losing) | Expected max drawdown grows like **log T** when profitable, **linearly in T** when losing -- a "phase transition." | [M1] |
| R3 | Comparing Calmar ratios (return ÷ max drawdown) | Common practice is to compare only over equal-length windows (typically three years), because no simple scaling law was known. | [M1] |
| R4 | ATR smoothing | Wilder's: next ATR = (prior ATR × 13 + current True Range) ÷ 14. | [W1] |

## 4. How our code compares to the literature -- and real bugs found

| id | What our code does | Evidence | Verdict |
|---|---|---|---|
| F1 | `attribute_drawdown` keeps only news items whose `symbol` field equals the ticker, timed by a `ts` field, weighted by `price_change_30m`. | **Tested against the real running news service (2026-09-24):** real articles have **no `symbol`, no `ts`, no `price_change_30m`**. They have `tickers`, `sort_ts`, `sentiment`. | **Confirmed bug: news attribution never matches anything.** Every live drawdown reports `news_driven_pct = 0`, `unexplained_pct = 1.0`, `contributing_events = 0`. The backtest detector (`detect_drawdown_episodes`) filters on `symbol` too, so its `formation_news` / `recovery_news` are also always empty. |
| F2 | Live `compute.py` uses a **fixed -2% threshold on every timeframe** (1min to 1D). | Drawdown depth scales with volatility and window length [M1]. | A 2% fall is a rare event on 1min bars and routine on a volatile stock's 1D bars. The ATR-adaptive detector that fixes this **already exists** in `drawdown.py` -- but only `backtest.py` uses it. |
| F3 | Peak = bar **high**, trough = bar **close**. | Drawdown is defined on one value series [M1]. | Mixing high and close makes every drawdown look deeper than a holder actually experienced (nobody sells at the intrabar high). |
| F4 | Spec and glossary promise "max drawdown duration, recovery time." | -- | **Not in the live output.** Duration, recovery price/speed and shape checkpoints exist only in `detect_drawdown_episodes` (backtest path). |
| F5 | `market_beta_pct` field. | -- | **Always 0.0** -- `compute.py` never passes market returns. Even if it did, the code would set a hardcoded 0.2, not a computed beta. |
| F6 | Even when matching works, `news_driven_pct = S ÷ (S + 0.1·n + 1)`, capped at 0.95, where BULLISH and BEARISH news weigh the same. | -- | An invented formula, not a statistical attribution; bullish news counts as "explaining" a drop just as much as bearish news. Treat it as a rough heuristic even after F1 is fixed. |
| F7 | ATR uses a plain average of True Range. | Wilder's is a recursive smoothing [W1]. | Known and documented in the code; minor. |
| F8 | Units: `drop_pct` is **percent** (-3.5 = -3.5%); `news_driven_pct` / `market_beta_pct` / `unexplained_pct` are **fractions** (0.3 = 30%) despite the same `_pct` suffix. | -- | Easy to misread. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

This angle writes **several rows per run**, told apart by `type`:

**`type: "drawdown"`** -- one row per detected drawdown:

| Field | Meaning |
|---|---|
| `peak_ts` / `peak_price` | When and where the fall started -- the bar's **high**. |
| `trough_ts` / `trough_price` | The lowest point reached -- a bar's **close**. |
| `drop_pct` | Depth in **percent**, negative (e.g. -3.5). |
| `lookback_from_ts` | `peak_ts` minus 24 hours, regardless of timeframe. Not used downstream. |

**`type: "attribution"`** -- one row, for the worst drawdown only:

| Field | Meaning |
|---|---|
| `peak_ts`, `trough_ts`, `drop_pct` | Same as the worst drawdown row. |
| `news_driven_pct` | Fraction (0-1). **Currently always 0** -- F1. |
| `market_beta_pct` | Fraction. **Always 0** -- F5. |
| `unexplained_pct` | Fraction. **Currently always 1.0** -- F1. |
| `contributing_events` | Number of news items matched. **Currently always 0** -- F1. |

**`type: "summary"`** -- one row, always last:

| Field | Meaning |
|---|---|
| `drawdown_count` | How many 2%+ drawdowns were found. |
| `max_drop_pct` | The deepest one, in percent. |

Every row also has `symbol`, `analysis_at`, `angle`. **Likely consequence,
not verified end-to-end:** the angle digest (`angles_tool.summarize_angle`)
keeps only the last row, i.e. the summary -- so the LLM probably only ever
sees `drawdown_count` and `max_drop_pct` from this angle.

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

This angle has **no `status` field**. Instead:

| Situation | What's written |
|---|---|
| No bars supplied | One row with `type: "status"`, `drawdown_count: 0`, `max_drop_pct: 0.0`. |
| Bars supplied, no 2%+ drawdown | One row with `type: "summary"`, `drawdown_count: 0`, `max_drop_pct: 0.0`. |
| Drawdowns found | `drawdown` rows + one `attribution` row + one `summary` row. |

The first two look almost identical -- only `type` tells "no data" apart
from "no drawdowns."

## 7. Comprehensive explanation  *(for humans only)*

**Two detectors in one folder.** `drawdown.py` has two separate
drawdown finders:
- `get_drawdowns` -- the older, simpler one. Fixed % threshold, tracks
  peak → trough, ends a drawdown when a later bar's high beats the old
  peak. **This is what the live angle (`compute.py`) uses**, with -2%.
- `detect_drawdown_episodes` -- the newer, richer one. Threshold =
  `-max(k × ATR%, 0.5%)` measured at the peak, so a volatile stock needs
  a bigger fall to count; tracks the full life of each episode (time to
  trough, speed, recovery time and speed, 25/50/75% shape checkpoints,
  news during formation vs. recovery). **Only `backtest.py` uses it**,
  sweeping k = 1.5, 2.0, 2.5, 3.0.

So the glossary and spec describe the richer detector, but the LLM gets
the simpler one's output.

**Why a fixed threshold is the wrong tool (F2).** Magdon-Ismail & Atiya
[M1] show that for a price with no trend, the expected worst drawdown
over a period T is about 1.25 × σ × √T. Two consequences: a stock with
twice the volatility should be expected to have drawdowns about twice as
deep, and a longer window always finds deeper drawdowns. A flat -2% cut
ignores both, so drawdown counts can't be compared across tickers or
timeframes. ATR-scaling (the newer detector) handles the volatility part.

**Why the news attribution returns nothing (F1).** Traced end to end: the
runner fetches articles from the news service; each real article carries
the ticker list in `tickers` and the time in `sort_ts`. The attribution
code instead looks for `symbol` and `ts`, which don't exist, so its
filter drops every article. It then reports "0% news, 100% unexplained"
for every drawdown -- indistinguishable, to a reader, from a genuine
finding that news didn't matter. It also weights events by
`price_change_30m`, which articles from this client don't carry either.

**ATR (A4, F7).** True Range is the largest of: today's high minus low,
|high minus yesterday's close|, |low minus yesterday's close| [W1].
Wilder smooths it recursively [W1]; our code uses a plain average of the
last 14, which reacts slightly differently but serves the same purpose.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| M1 | Magdon-Ismail & Atiya, "An Analysis of the Maximum Drawdown Risk Measure" (published as "Maximum drawdown," *Risk*, 2004) -- author's PDF, pp. 1-3 | MDD definition (peak to following bottom); expected MDD: 1.2533σ√T at zero drift, ~log T positive drift, ~linear negative drift; Calmar compared over equal windows (typically three years). | https://www.cs.rpi.edu/~magdon/ps/journal/drawdown_RISK04.pdf |
| W1 | StockCharts ChartSchool, "Average True Range (ATR)" | True Range's three components; Wilder smoothing formula; introduced by J. Welles Wilder, *New Concepts in Technical Trading Systems*, 1978. | https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-true-range-atr |
| -- | Direct test against the running `news-api` service via `NewsClient.get_ticker_news("AAPL")` inside `vinu-components-initial-analysis-api-1` | Real article keys: `tickers`, `sort_ts`, `sentiment`, ... -- no `symbol`, `ts`, or `price_change_30m`. | (local test, 2026-09-24) |
