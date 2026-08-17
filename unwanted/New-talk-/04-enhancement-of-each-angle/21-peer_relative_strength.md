---
name: angle-21-peer_relative_strength
status: decided
purpose: discussion and enhancement proposal for the `peer_relative_strength` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/peer_relative_strength/`.
---

# 21 — peer_relative_strength

**Title (from spec.yaml):** Peer Relative Strength

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/peer_relative_strength/`
- Not a forecaster, not a pretrained/fallback situation — classical
  rolling statistics (63-day rolling correlation, 20-day relative/excess
  return vs. a peer basket), no `model_backend` question applies.
- **Real, working, cheap** — confirmed real code (not a stub): computes
  rolling correlation and excess return against every peer, aligned on a
  common dated index with forward-fill for gaps, cheap enough to run on
  every request.
- **Honest limitation, confirmed from code, kept as-is rather than
  silently glossed over**: "peers" here means whatever's on the caller's
  **watchlist** (`price_client.get_watchlist()`), not a curated sector/
  industry-matched peer group. A watchlist can contain unrelated symbols,
  which would dilute what "peer" means for this signal. Not fixed in
  this pass — see §7.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md),
  applied partially — see §3/§5 for why session tagging doesn't apply
  here.

## 2) One-line definition

Peer Relative Strength tracks, day by day, how closely a stock moves
together with a basket of other stocks on its watchlist (rolling
correlation) and how much better or worse it's been doing than that same
basket lately (a rolling excess return) — and, as proposed here, checks
whether either of those numbers actually says anything about what the
stock does *next*, not just what it's already done.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Model backend | not applicable | classical rolling statistics, no pretrained/fallback question |
| Rolling correlation window | 63 trading days (code default `ROLLING_CORR_WINDOW`, kept as-is) | ~1 trading quarter — a standard, defensible window size for rolling correlation in practice |
| Relative return window | 20 trading days (code default `RELATIVE_RETURN_DAYS`, kept as-is) | ~1 trading month; symbol's cumulative return minus the peer basket's cumulative return over the same window |
| Peer basket weighting | equal-weighted mean of peer returns (code default, kept as-is) | simple, transparent baseline weighting — not market-cap-weighted or otherwise adjusted |
| Peer definition | **watchlist-derived, not sector/industry-curated** (code's real behavior, kept as-is) | honest limitation, not fixed in this pass — see §7 |
| Sampling cadence | every 5 bars (code default `SAMPLE_EVERY_N_BARS`, kept as-is) | reduces heavily overlapping/autocorrelated rows from a daily rolling window — roughly weekly cadence instead of one highly redundant row per trading day |
| Min observations | 65 trading days (`ROLLING_CORR_WINDOW + 2`, code's own real derived floor) | not artificially raised to the N=100 convention — this is already a real, derived minimum tied directly to the rolling window itself, not an arbitrary candle-count floor like the forecasting angles |
| Timeframe | 1min, 5min, 15min, 1H, 4H, 1D | **updated**: widened to the standard 6, same as every other angle — supersedes the earlier 1D-only decision, which had argued a 63-bar rolling correlation on finer bars would be a much noisier, different-length window rather than the same signal at finer resolution |
| Time-based tagging | day-of-week / week-of-month / month / quarter only — **no session/subsession tags** | one row already = one trading day's close-to-close computation; there's no intraday session to distinguish for a signal that only exists once per day |
| **Proposed enhancement — forward-return validation** | for each sampled (symbol, peer, date) row, also compute the *actual* forward N-day return (5/10/20 trading days after that date) during backtest analysis, then test whether `relative_return_20d`/`correlation` actually correlates with what happens next | turns this from a raw descriptive feature into a validated signal — see §7 for why this was the main gap worth closing |
| Forward-return correlation significance | Pearson correlation + bootstrapped 95% CI between `relative_return_20d` and forward N-day return, same method already used in `news_price_causality`'s correlation module | reuses an already-decided, already-real technique rather than inventing a new one |
| Baseline comparison | none needed — same reasoning as `news_price_causality` | the bootstrapped CI (does it exclude 0) is itself the "different from noise" check; a separate naive baseline doesn't apply to a correlation test |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca (daily bars for symbol + watchlist peers) | same as other angles |
| Symbol scope | parameterized — specific ticker (peers come from that call's watchlist) | matches code's real interface |

## 4) Example — what results look like

**Raw sampled row (as the code produces today):**

```
symbol: AAPL
date: 2024-05-15
peer_symbol: MSFT
correlation: 0.62
relative_return_20d: 0.031
```

**After tagging** (day-of-week / week / month / quarter only, no
session):

```
+ day_of_week: Wednesday
+ week_of_month: 3
+ month: May
+ quarter: Q2
```

**Proposed forward-return validation row (new, computed during backtest
analysis, not stored as a real-time feature):**

```
symbol: AAPL
peer_symbol: MSFT
date: 2024-05-15
relative_return_20d: 0.031
forward_return_20d: 0.018
```

**After aggregation (queryable key, testing predictive value):**

```
AAPL-vs-MSFT-Q2-2024 = corr(relative_return_20d, forward_return_20d) = 0.14, CI [0.02, 0.26], n=48
→ weak positive: mild momentum continuation, not mean-reversion, in this slice
```

(Illustrative — the actual sign/strength is a real, measured finding
once this runs, not assumed in advance; could just as easily come back
near-zero or negative.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per (symbol, peer, sampled
  date), tagged with day-of-week/week/month/quarter only (no session).
  This is the existing computation, unchanged.
- **New: forward-return validation table**: computed once per backtest
  run (not per live request, since it needs future data relative to each
  row's date) — joins each Layer 1 row to its own forward N-day return,
  then aggregates the correlation + bootstrapped CI per (symbol, peer,
  quarter) slice, same granularity reasoning as `news_price_causality`'s
  aggregate tests (day/week slices would be too thin for a meaningful
  correlation).
- **Layer 2/3**: same shared query pattern as other angles for the raw
  correlation/relative-return rows; the forward-return validation table
  is queried directly since it's already an aggregate.

## 6) What we will achieve / how to use it

- Turns a currently-descriptive-only feature into a **validated signal**
  — an honest answer to "does this stock's peer co-movement/relative
  strength actually predict anything," not just a running computation
  nobody has checked the usefulness of.
- If forward-return correlation turns out near-zero, that's a genuine,
  useful negative result (same spirit as `news_price_causality`'s honest
  "direction isn't predictable" finding) — better to know that than to
  keep feeding an unvalidated feature into downstream decisions.
- A real, cheap, always-available cross-sectional signal — distinct in
  kind from every price-forecasting angle discussed so far (this is
  relative/peer-based, not absolute-price-based).

## 7) Deeper rationale

**Why forward-return validation was the main gap worth proposing:** as
written, this angle computes real numbers but never checks whether they
mean anything predictively — it's a feature generator, not a tested
signal. Every other genuinely analytical angle discussed so far
(ARIMA's CI-coverage, `news_price_causality`'s Granger/correlation/
classifier) exists specifically to answer "is this real, or is this
noise." Leaving `peer_relative_strength` as pure description would be
inconsistent with that standard — the natural, low-cost fix is checking
correlation against each row's own future outcome, which needs no new
data source, just the price history already being pulled.

**Why the watchlist-as-peers limitation isn't being fixed here:**
building a real sector/industry peer-mapping system (e.g. GICS
classification, correlation-based clustering) is a meaningfully larger
scope than this angle-by-angle discussion pass covers, and would need
its own data source decision. Flagging it honestly (rather than silently
treating "watchlist" as if it meant "true peers") is the more accurate
move for now — same principle as flagging any other real limitation in
this project rather than glossing over it. If the watchlist happens to
already be sector-coherent for a given user, results will still be
meaningful; if not, that's a known, documented caveat, not a hidden bug.

**Why session/subsession tagging doesn't apply:** the standard tagging
rule was designed for angles that produce a value per intraday candle.
This angle produces exactly one row per trading day per peer — there is
no intraday variation to tag, so applying session/subsession here would
be tagging a dimension that doesn't exist in the data.

**Why no separate naive baseline:** identical reasoning to
`news_price_causality` — a correlation test's own confidence interval
already answers "is this different from noise," the same role a naive
baseline plays for a price forecaster.

**Open/unresolved:** the actual forward-return predictive value (if any)
is unknown until the backtest runs — §4's numbers are illustrative. Also
open: whether "watchlist" is an acceptable long-term peer definition or
should eventually be replaced with a real sector/industry mapping — noted
but intentionally out of scope for this pass.
