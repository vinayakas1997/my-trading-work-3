---
name: angle-19-news_price_causality
status: decided
purpose: discussion and enhancement proposal for the `news_price_causality` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/`.
---

# 19 — news_price_causality

**Title (from spec.yaml):** News-Price Causality

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py`,
  `granger.py`, `correlation.py`, `significance_model.py`, `impact.py`,
  `novelty.py`, `regime_features.py` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/`
- **Not a forecaster, not a pretrained/fallback situation at all** —
  classical statistics (real `statsmodels` Granger causality test, real
  `scipy` Pearson correlation with bootstrapped CIs) plus one leakage-safe
  XGBoost classifier trained fresh per run. No `model_backend` question
  applies here.
- **Genuinely rigorous, verified directly in the code, not assumed:**
  - Event-study abnormal returns use a **market-factor control against
    SPY** (falls back to mean-adjusted only if SPY data is unavailable),
    so a market-wide move doesn't get misattributed to a coincidentally-
    timed article.
  - The significance classifier's docstring documents its own **caught
    and fixed leakage bug**: an earlier version trained on features that
    indirectly encoded the answer, reported a "7-8x lift"; removing the
    leaked features dropped that to the real, honest number now shipped.
  - The docstring also documents a **confirmed negative result, reported
    honestly rather than hidden**: predicting the *direction* of a price
    reaction from sentiment was tested twice (rule-based, then FinBERT)
    on real symbols and found ~50% sign-agreement (coin-flip, all
    correlations p > 0.1) — the model only claims to predict
    magnitude/surprise, not direction.
- **External literature check**: event studies + Granger causality are
  established, legitimate techniques for this exact question, but the
  real-world literature is genuinely mixed — some studies find real
  news→price predictability around news-volume peaks/events, others find
  no significant aggregate causality. This code's own honest
  no-direction-signal / real-magnitude-signal finding lines up with that
  mixed picture rather than overclaiming. See sources at the end.
- No shared tagging piece applies uniformly — see §5 for why this angle
  needs two different granularities instead of the standard single
  per-row tagging scheme.

## 2) One-line definition

News-Price Causality statistically tests whether news actually moves a
stock's price — checking whether news volume predicts price changes
before they happen (Granger causality), how strongly news and price move
together (correlation), how long it takes for news to show up in price
(lag analysis), and which specific articles are likely to cause a real,
outsized price reaction (a classifier using only information available
the instant the article is published).

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | not applicable | classical statistics + one leakage-safe XGBoost classifier trained fresh per run; no pretrained/fallback question |
| Timeframes | 1min, 5min, 15min, 1H, 4H, 1D | **updated**: widened to the standard 6, same as every other angle — supersedes the earlier decision to keep only the code's real set (1min/15min/1H/1D, no 5min/4H), which had argued widening was a no-op here since Granger/correlation/lag always resample to hourly buckets regardless of requested timeframe |
| Event-study granularity | 1min bars, per-article | matches code exactly — this is the only timeframe pass that computes per-article impact/abnormal-return rows, to avoid tripling identical rows across timeframe passes |
| Market-factor control | SPY-based abnormal return, mean-adjusted fallback if SPY unavailable | code default, kept as-is |
| Granger causality | `statsmodels.tsa.stattools.grangercausalitytests`, max_lag=12 hours, causal if best p < 0.05 | code default, kept as-is; needs ≥17 hourly buckets to run at all (`max_lag + 5`), a real, non-arbitrary floor already in the code |
| Correlation | Pearson (news-count/return, sentiment/return, news-volume/\|return\|) with bootstrapped 95% CI (500-1000 resamples) | code default, kept as-is; needs ≥5 merged hourly buckets |
| Lag analysis | correlation at [0, 15, 30, 60, 120] minute offsets, best lag = strongest \|correlation\| | code default, kept as-is |
| Significance classifier | XGBoost (`n_estimators=200, max_depth=3`), chronological 70/30 train/test split (never random, to avoid future-leakage), needs ≥130 usable rows with ≥10 train-positives and ≥3 test-positives | code default, kept as-is — these thresholds are already real, derived minimums, not arbitrary like the N=100 convention used for candle-count forecasters |
| Significance classifier features | sentiment_score, finbert_score, novelty_score, ticker_count, category, priority, session, is_primary, plus optional pre-event regime features (vol_21d, ret_20d, regime_feature) | code default, kept as-is — explicitly excludes impact_label/price_change_* (the leakage the code already caught and fixed) |
| Time-slicing for aggregate tests (Granger/correlation/lag/significance-eval) | per calendar **quarter** only, not the full session/day/week breakdown | the standard 5-tag scheme (session/day-of-week/week/month/quarter) would leave too few hourly buckets per slice to satisfy the code's own minimum-sample checks (a single trading day has ~7 hourly buckets, well under Granger's 17-minimum); quarters (~450+ trading hours) are the finest slice that stays statistically meaningful for these specific tests |
| Time-slicing for per-article impact rows | full standard scheme (session/day-of-week/week/month/quarter), per [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) | each impact row has its own real timestamp, same as any other angle's per-row forecast — the standard tagging applies directly here, unlike the aggregate tests |
| Baseline comparison | none needed — built into each test's own statistic | Granger's p<0.05 threshold, correlation's bootstrapped CI (does it exclude 0), and the classifier's own base_rate (unconditional test-set positive rate) already answer "is this different from noise/doing nothing" — a separate naive-random-walk baseline (used for the price-forecasting angles) doesn't apply to a causality test |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca (price bars) + vinu-news (articles) | both already required inputs to `compute()` |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |

## 4) Example — what results look like

**Per-article impact row (1min pass, full standard tagging):**

```
symbol: AAPL
article_id: a_48213
type: impact
ts: 2024-05-15T13:42:00Z
session: ny
subsession: markethours
day_of_week: Wednesday
week_of_month: 3
month: May
quarter: Q2
price_change_5m: 0.42
price_change_15m: 0.61
abnormal_return: 0.38
ar_significant: true
novelty_score: 0.71
significance_score: 0.64
significance_score_sample: test
```

**Per-(symbol, quarter) aggregate result:**

```
symbol: AAPL
quarter: 2024-Q2
type: granger
granger_causes_prices: true
best_lag_minutes: 180
p_value: 0.021
sample_size: 456

type: correlation
news_return_corr: 0.087
corr_p_value: 0.041
corr_ci_lower: 0.014
corr_ci_upper: 0.159
sentiment_return_corr: 0.012
sample_size: 456

type: significance_model_eval
n_train: 812
n_test: 348
auc: 0.68
top_decile_lift: 2.9
base_rate: 0.11
```

## 5) Storage, querying, API shape

**Two separate storage granularities, not one — this angle genuinely
doesn't fit the single-per-row pattern the forecasting angles use:**

- **Per-article impact rows** (Layer 1/2/3, same pattern as every
  forecasting angle): raw tagged rows per article per
  [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md),
  Layer 2 precomputed session+subsession+timeframe aggregates (e.g. mean
  abnormal return, % significant), Layer 3 on-demand custom slices.
- **Per-(symbol, quarter) aggregate test results** (new pattern, specific
  to this angle): one row per symbol per quarter per test type (granger /
  correlation / lag / significance_model_eval), stored directly — these
  values are already the aggregate, there's no finer raw row to derive
  them from without rerunning the test on a re-sliced window, so Layer 1
  and Layer 2 collapse into one for this piece. Querying "does causality
  hold in NY session only" isn't offered — that slice wouldn't have
  enough hourly buckets to be a real answer.

## 6) What we will achieve / how to use it

- A real, reproducible answer to "does news actually move this stock's
  price" per symbol per quarter — not a one-off run, but tracked over
  time so causality strength/stability across market regimes becomes
  visible (e.g. does Granger-causality hold in volatile quarters but not
  calm ones).
- A prioritization signal (`significance_score`) for which articles are
  worth attention *before* the price confirms it — with the model's own
  honest AUC/lift numbers stored alongside every run, so nobody trusts a
  score without also seeing how reliable that particular symbol's model
  actually was.
- A permanent, honest record that direction-prediction from sentiment
  doesn't work (already tested, already documented) — preventing this
  from being silently re-attempted or misrepresented as a working
  feature downstream.
- Since this is the first angle to combine full per-row tagging with a
  new coarser per-quarter aggregate pattern, it establishes that second
  pattern for any future angle that needs statistical-test-style
  aggregation instead of per-forecast scoring.

## 7) Deeper rationale

**Why timeframes aren't widened to the standard 6:** the widening
convention exists because a price forecaster's actual output changes
meaningfully with timeframe (1min ARIMA is a genuinely different
question than 1day ARIMA). Here, Granger/correlation/lag always operate
on hourly-resampled data regardless of what timeframe was requested, and
the event study is pinned to 1min bars for a fixed, real reason (5-15min
window resolution). Adding 5min/4hr passes would compute the exact same
hourly-resampled numbers a second and third time for no new information
— pure waste, not a missed opportunity for comparability.

**Why quarter-level slicing for the aggregate tests instead of the full
tagging scheme:** this isn't a stylistic choice, it's forced by the
tests' own real minimum-sample requirements already in the code (Granger
needs ≥17 hourly buckets, the significance classifier needs ≥130 usable
rows with real positive counts on both sides of a chronological split).
A single day or session slice wouldn't clear those bars — reporting a
Granger result from an underpowered slice would be reporting noise
dressed up as a finding, exactly the kind of thin-slice trap the shared
tagging rule's own "always show `n`" principle warns against.

**Why no naive baseline is needed here:** the naive-random-walk baseline
exists for price forecasters to answer "is this better than doing
nothing." A causality test's whole purpose is already that same
question, built into its own statistic — a Granger p-value, a
correlation's confidence interval, and a classifier's lift-over-base-rate
are all already "compared to noise" by construction. Bolting on a
separate naive baseline would be redundant, not additive.

**Why this angle deserved a fuller code read than most others before
deciding anything:** unlike the fallback-proxy or trained-from-scratch
angles (where one `compute.py` file tells the whole story), this one
spans multiple real submodules (event study, Granger, correlation,
significance model) each with its own real methodology and its own
already-resolved correctness issue (the leakage bug, the SPY control,
the honest negative result) — getting the design right required actually
reading `granger.py`/`correlation.py`/`significance_model.py`, not just
the top-level `compute.py`.

**Open/unresolved:** none on the methodology itself — it's already
real, tested, and honestly self-documented. What's open is purely
operational: this design hasn't been run against the full 2022-2026
dataset yet, so the *actual* per-symbol/per-quarter Granger-causality and
lift numbers aren't known until the backtest actually runs — the
examples in §4 are illustrative, not measured.

Sources checked for external validity of the methodology:
- [Investor Sentiment and Market Movements: A Granger Causality Perspective (arXiv:2510.15915)](https://arxiv.org/pdf/2510.15915)
- [The Effects of Twitter Sentiment on Stock Price Returns (arXiv:1506.02431)](https://arxiv.org/pdf/1506.02431)
