---
name: angle-01-arima
status: decided
purpose: discussion and enhancement proposal for the `arima` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/arima/`.
---

# 01 — arima

**Title (from spec.yaml):** ARIMA Classical Statistical Baseline

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` / `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/arima/`
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)

## 2) One-line definition

ARIMA is a classical statistics formula that looks at a stock's past prices
and predicts the very next price, along with a range of how confident it is
about that prediction — no machine learning or pretraining involved, it's
refit fresh every time from scratch.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Min observations (N) | 100 candles | same for every timeframe — "100 candles of whatever timeframe", not 100 units of real time |
| Order (p, d, q) | adaptive, chosen per fit via AIC grid search | not fixed — different timeframes/series have different noise/trend, forcing one order would bias comparisons |
| Forecast horizon | 1 step ahead | fixed across all timeframes for comparability |
| Confidence level | 95% | matches existing `compute.py` output |
| Hit definition | actual next close falls inside the model's own confidence interval (CI-coverage) | rejected a fixed ±5% band — see §7 |
| Backtest method | walk-forward (rolling refit + forecast + check, slide forward, repeat) | single fits are too noisy to trust |
| Refit cadence (N) | flexible per timeframe, named constants (`N_1MIN`, `N_5MIN`, `N_1H`, `N_4H`, `N_1D`) | refit every step for 1D/4H/1H; refit every N candles for 1min/5min to keep compute sane — actual cadence to be set after benchmarking real fit time |
| Timeframes | 1min, 5min, 15min, 1hr, 4hr, 1day | |
| Date range | 2022-01-01 → 2026-Q2 | ~4.5 years |
| Data source | Alpaca | full-depth 1min/5min history confirmed available |
| Baseline comparison | naive random-walk (forecast = last close) run through the same backtest | needed to check ARIMA actually beats doing nothing |
| Symbol scope | parameterized — specific ticker runs just that one; no ticker runs all tracked tickers | results stored either way, tagged with symbol |
| Time-based tagging | session / day-of-week / week / month / quarter | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) — not ARIMA-specific |

## 4) Example — what one result looks like

**Single forecast row (from the walk-forward backtest, before tagging):**

```
symbol: AAPL
timeframe: 1D
candle_ts: 2024-05-15T13:30:00Z
order: {p: 1, d: 1, q: 1}
aic: 812.4
forecast: 142.30
confidence_interval: [140.10, 144.50]
confidence_level: 0.95
actual_close: 142.80
hit: true
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
NY-MARKETHOURS-1330-2000-1D = 88.5% CI-coverage (n=912 forecasts)
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: every walk-forward forecast, one row per
  step, stored with full tag columns (see §4). This is the source of
  truth; never overwritten.
- **Layer 2 — precomputed common keys**: after each backtest run,
  precompute the default aggregate keys (session + subsession +
  timeframe) with their `n`, so common lookups don't require recomputing
  from raw rows every time.
- **Layer 3 — on-demand query service**: builds any custom key
  combination (adding day-of-week, week, quarter, etc.) at query time from
  Layer 1, for anything not already in Layer 2. Always returns `n`
  alongside the metric.

Backtests are run once and cached — not recomputed on every use. A rerun
only happens if the underlying price data changes or a config parameter
(N, order search space, tag definitions) changes.

Every stored/precomputed/queried result carries enough metadata to be
fully self-describing: `symbol, timeframe, N, date_range, order or order
search space, hit_rate or ci_coverage, n_forecasts, run_timestamp`.

Full tagging mechanics (UTC base, session UTC ranges, key format, storage
layers) are defined once in [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)
and reused as-is here — not redefined per angle.

## 6) What we will achieve / how to use it

- A real, statistically grounded answer to "which timeframe is ARIMA most
  reliable at" — replacing guesses like "15min gave 80%" with backtested
  CI-coverage numbers with sample counts attached.
- A per-session/day/week/month/quarter breakdown of where ARIMA's
  forecasts are most trustworthy — e.g. spotting that a timeframe or
  session is systematically overconfident (CI-coverage far below 95%) or
  underconfident (far above 95%).
- A baseline number (vs. naive random-walk) to judge whether ARIMA is
  actually adding value at each timeframe, not just producing plausible-
  looking numbers.
- Since the tagging/storage/query design is shared, not ARIMA-specific,
  the same infrastructure carries over directly to the other 30 angles
  once each is discussed — this angle's backtest is effectively the
  reference implementation for that shared machinery.

## 7) Deeper rationale

**Why N=100, not 30:** the code's current floor (`_MIN_OBSERVATIONS = 30`
in `compute.py`) is below even the loose minimum found in general
time-series literature. ARIMA/Box-Jenkins methodology (Box & Jenkins,
*Time Series Analysis: Forecasting and Control*, 1970) doesn't prescribe
one universal sample-size number — there's no single citable "the paper
says N" — but the commonly cited practical guidance is ~50 minimum,
100+ preferred for stable parameter estimates, especially once
differencing (d>0) is involved. 100 was chosen as a clean, defensible
floor above the loose minimum, applied uniformly so results are
comparable across timeframes.

**Why 100 candles of whatever timeframe, not 100 units of real time:**
using a fixed candle count keeps the experiment question clean and
well-defined — "at a fixed candle-count, does resolution (timeframe)
affect ARIMA's forecast reliability?" — rather than conflating resolution
with how much history is fed in.

**Why CI-coverage instead of a fixed ±5% band:** ARIMA already produces a
95% confidence interval for free on every forecast — using it as the hit
criterion needs no invented threshold. A fixed percentage band like ±5%
would bias the comparison across timeframes, since volatility differs
hugely by resolution (a 1-minute candle might typically move ~0.05-0.1%,
a daily candle 1-3%+) — a flat band would make fine timeframes look
artificially great and coarse timeframes look artificially bad. CI-
coverage is volatility-aware by construction: the interval widens/narrows
based on that specific window's estimated variance.

**Why walk-forward instead of a single fit:** a single ARIMA fit +
1-step forecast is one data point — too noisy to draw conclusions from.
Rolling the fit forward across the whole history and checking hundreds to
thousands of individual forecasts gives a statistically meaningful
hit-rate/CI-coverage number instead of one lucky or unlucky result.

**Why adaptive (p,d,q) instead of one fixed order:** forcing a single
order across all timeframes/series would itself bias the comparison —
different series have different underlying dynamics. Letting AIC pick the
best order per fit keeps each individual fit honest, while N, horizon, and
CI-definition stay fixed so the *comparison* across timeframes stays fair.

**Why a naive baseline matters:** price series are often close to a
random walk, and ARIMA can look "good" on paper while barely beating a
model that just predicts "next price = last price." Running the same
walk-forward backtest with a naive forecast alongside ARIMA is what turns
"ARIMA scored 85% CI-coverage" into "ARIMA is actually adding value" or
"ARIMA isn't doing much more than doing nothing."

**Compute cost caveat (open, not yet resolved):** an early estimate
suggested a full per-step refit across ~440,000 1-minute candles (17-model
grid search per step) could take on the order of days — but this was an
unverified back-of-envelope guess, not a measurement. Before committing to
a refit cadence for 1min/5min, this needs to be benchmarked directly
(time one fit on a real 100-candle window, multiply out) rather than
trusted as-is.
