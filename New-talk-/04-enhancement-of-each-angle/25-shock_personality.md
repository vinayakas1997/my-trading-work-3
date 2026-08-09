---
name: angle-25-shock_personality
status: decided
purpose: discussion and enhancement proposal for the `shock_personality` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/shock_personality/`.
---

# 25 — shock_personality

**Title (from spec.yaml):** Shock Personality

## 1) Status

- Discussed: 2026-08-08
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/shock_personality/`.
- Not a forecaster — post-shock behavioral characterization for a single
  symbol: does it tend to fill its gaps, how persistent is its
  volatility (real GARCH), does its post-shock drift tend to continue.
- **Confirmed bug #1 — same leak class as `regime_analysis`/
  `shock_clustering`, independently reimplemented here, not shared code.**
  `_detect_gap_shocks`'s `gap_mean`/`gap_std` are computed over the
  **entire** bars series, a full-history constant. This is a near-
  duplicate of `shock_clustering`'s own gap-detection function (same
  z-score logic, already slightly diverged in output shape) — two
  independent copies of the same bug, not one shared bug. Fixed here the
  same way: rolling window instead of a full-sample constant. See §7 for
  why a live-deployable metric requires this fix, not just backtest
  correctness — the exact question raised and answered earlier in this
  discussion.
- **Confirmed bug #2 — real computation, silently discarded.**
  `_compute_drift_persistence` computes per-shock post-event return
  autocorrelation (`post_shock.autocorr(lag=l)` for lags 1-9), but the
  values are only ever used to check "is there at least one non-NaN
  result" — the actual autocorrelation numbers are thrown away, never
  reported. Same "computed but discarded" pattern as
  `drawdown_deep_dive`'s dead `lookback_hours` field.
- **Confirmed bug #3 — real computation, silently discarded.**
  `_cross_reference_news` tags every detected shock with `has_news`/
  `nearest_news_days`, but `compute()`'s final output only reports an
  aggregate `n_shocks` count — the per-shock news information never
  reaches storage. A real, answerable question ("do news-driven shocks
  behave differently than noise shocks") is sitting unused in the code.
- **Code-hygiene note, not fixed here**: this angle and `shock_clustering`
  independently reimplement near-identical gap/vol-spike shock detection.
  Worth factoring into one shared module eventually (same spirit as
  `patchtst`/`lpatchtst` sharing `PatchEncoderBranch`), but treated as a
  future refactor, not part of this design — each angle's own leak fix
  is applied directly regardless.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md),
  applied to the new per-shock rows — see §5.

## 2) One-line definition

Shock Personality builds a behavioral profile for one stock's unusual
single-day moves — does it tend to fill its price gaps back in, does its
volatility stay elevated for a while after a shock or fade quickly (real
GARCH), and does a shock's direction tend to keep drifting or reverse —
now also split by whether news was actually nearby when each shock
happened.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Gap-shock detection | `abs(gap_z) > 2.0`, **fixed to rolling** `gap_mean`/`gap_std` (21-day, matching the vol-spike trigger's own window) instead of the full-sample constant | closes confirmed bug #1 |
| Gap-shock timeframe scope | 1min, 5min, 15min, 1H, 4H, 1D | **updated**: widened to the standard 6, same as every other angle — supersedes the earlier 1D-only decision, which had argued a "gap" is specifically the close-to-open session-boundary jump and widening would mostly just re-measure the same daily event redundantly on intraday bars |
| Vol-spike detection | `vol_z > 2.0` on rolling 21-day `(high-low)/close` (code default, kept as-is, already correct — no leak here) | |
| Vol-spike timeframe scope | 1min, 5min, 15min, 1H, 4H, 1D | **updated**: widened to the standard 6, same as every other angle (already partially widened from 1D-only to 15min/1H/1D; now completed to the full 6) — "was this bar's range unusual for its own timeframe" is meaningful at any resolution |
| **New: post-shock autocorrelation reported, not discarded** | mean lag-1-through-9 return autocorrelation following each shock, averaged across shocks, alongside the existing sign-streak `drift_persistence_days` | closes confirmed bug #2 — uses data already being computed instead of throwing it away; gives a continuous, non-truncating complement to the existing crude "streak until first sign flip" measure |
| **New: per-shock news presence surfaced, not discarded** | every stored shock row carries `has_news`/`nearest_news_days` (already computed by `_cross_reference_news`) | closes confirmed bug #3 |
| **New: gap_fill_rate and drift metrics split by news presence** | in addition to the existing overall aggregate, also report gap_fill_rate/drift_persistence separately for `has_news=true` vs `has_news=false` shocks, each with its own `n`/CI | the natural use of the now-surfaced news data — a real, answerable question ("do news-driven shocks fill less / drift more than pure noise shocks") this angle can now actually address |
| Gap fill window | 5 days (code default, kept as-is) | a reasonable, documented default — not deeply validated, flagged as open to a future robustness sweep, same spirit as other undecided window sizes in this project |
| Vol persistence | real GARCH alpha + beta via `vinu_tools.compute.risk.volatility.garch_volatility` (code default, kept as-is) | already a real, shared, validated function — same one the `garch` angle itself uses — no change needed |
| Drift max lag | 20 days (code default, kept as-is) | reasonable, unvalidated default, same treatment as gap fill window |
| CI method | t-distribution, `n<2` → `insufficient_sample` (code default, kept as-is) | matches `pnl_attribution`'s exact same CI convention — consistent statistical treatment across this codebase |
| **New: thin-sample caution below the hard floor** | results with `2 ≤ n < 10` are still computed (not blocked) but flagged/documented as thin — interpret cautiously | `n≥2` is enough to technically compute a t-CI but not enough to trust it; same "always show n, don't over-trust a thin slice" discipline used everywhere else in this project, applied as guidance rather than a second hard cutoff |
| Min observations | 21 candles (real floor — the rolling window's own requirement, not the arbitrary N=100 convention) | this angle's actual gating constraint is how many shocks get detected over the range, not the raw candle count |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca (price) + shared news pipeline | same as other angles |
| Symbol scope | parameterized — specific ticker | matches code's real interface |
| Time-based tagging | gap-shock rows: day-of-week/week/month/quarter only (no session — 1D-only, same reasoning as `peer_relative_strength`/`regime_analysis`). Vol-spike rows at 15min/1H: full standard tagging including session/subsession; at 1D: day/week/month/quarter only | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) — applied differently per shock type/timeframe since only the intraday vol-spike rows have a real session to tag |

## 4) Example — what results look like

**Per-shock row (new, tagged, with news cross-reference surfaced):**

```
symbol: AAPL
timeframe: 1D
date: 2024-05-14
type: gap
magnitude: -0.034
z_score: -2.41
has_news: true
nearest_news_days: 0
+ day_of_week: Tuesday
+ week_of_month: 2
+ month: May
+ quarter: Q2
```

**Aggregate results (existing shape, kept, now with news-split added):**

```
symbol: AAPL
n_shocks: 22
gap_fill_rate: {mean: 0.61, n_observations: 15, confidence_interval: [0.44, 0.78]}
gap_fill_rate_news: {mean: 0.52, n_observations: 9, confidence_interval: [0.28, 0.76]}
gap_fill_rate_no_news: {mean: 0.74, n_observations: 6, confidence_interval: [0.51, 0.97], note: "thin sample, n<10"}
vol_persistence: {alpha: 0.08, beta: 0.87, persistence: 0.95, status: "ok"}
drift_persistence_days: {mean_days: 2.3, n_observations: 22, confidence_interval: [1.6, 3.0]}
drift_mean_autocorr: {mean: 0.14, n_observations: 22, confidence_interval: [0.02, 0.26]}
```

(Illustrative — the actual news-split direction/strength is a real,
measured finding once this runs, not assumed in advance.)

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows (new)**: one row per detected shock
  (gap or vol-spike), carrying type/magnitude/z_score/has_news/
  nearest_news_days, tagged per §3's rule.
- **Layer 2 — precomputed common keys**: the existing per-symbol
  aggregate (gap_fill_rate, vol_persistence, drift_persistence), plus
  the new news-present/news-absent split versions, each carrying `n`.
- **Layer 3 — on-demand query service**: same shared pattern as other
  angles, e.g. "gap fill rate for shocks in Q2 2024 only," composed from
  Layer 1.

## 6) What we will achieve / how to use it

- A real, live-deployable shock detector (post-leak-fix) instead of one
  that could only ever run as a historical report — see §7.
- Two complementary drift-persistence views (sign-streak and mean
  autocorrelation) instead of one crude measure that truncates at the
  first sign flip even when an underlying drift is real.
- An actual answer to whether news-driven shocks behave differently than
  noise shocks for this specific stock — previously computed and
  silently thrown away, now a real, queryable comparison.
- A genuinely different, per-symbol "behavioral profile" — distinct from
  every other angle discussed so far, useful for position-sizing/risk
  decisions specific to how a given stock tends to behave after a shock.

## 7) Deeper rationale

**Why the rolling-window fix matters beyond backtest correctness (this
came up directly in discussion before writing this file):** a full-sample
statistic can't be computed live — at any real point in time, "the whole
sample" includes days that haven't happened yet. A system built on the
leaky version could only ever run as a one-time historical report, never
as an actual live "is today shocking" check. The rolling version uses
only trailing data, so the exact same calculation that runs in a backtest
can run unchanged in production every day — that's the actual point of
the fix, not just statistical hygiene.

**Why gap detection stays 1D-only while vol-spike detection widens:**
these two triggers have genuinely different relationships to time
granularity, so they don't get the same treatment. A gap is inherently
about the boundary between sessions; measuring it on intraday bars would
mostly just re-detect the same daily event at the session's first bar
while producing meaningless near-zero readings everywhere else. A
volatility spike, by contrast, is a property of any individual bar
relative to its own recent history — genuinely different information
exists at 15min/1H that a 1D-only view can't see (a sharp intraday move
that resolves by the close).

**Why the autocorrelation values are surfaced instead of just fixing the
"discarded" issue by deleting the computation:** the values were already
being computed at real cost — throwing them away after computing them is
worse than either using them or not computing them at all. Since
autocorrelation is a genuinely more informative, continuous view of
post-shock persistence than a sign-streak that stops dead at the first
reversal, reporting both together gives a fuller picture than either
alone.

**Why the news split is added instead of just exposing has_news as a raw
per-row field:** a raw field nobody aggregates is only marginally more
useful than not having it. Actually splitting the two existing aggregate
metrics (gap fill, drift) by news presence turns previously-wasted
computation into a real, answerable comparison — consistent with this
project's general principle of using real computed signal instead of
letting it sit unused.

**Why the code-duplication with `shock_clustering` isn't fixed in this
pass:** consolidating both angles' shock-detection logic into one shared
module is a real, worthwhile cleanup, but it's a cross-angle refactor,
not a decision that belongs inside either angle's own design discussion.
Flagged honestly rather than silently ignored or scope-crept into a
bigger change than this pass covers.

**Open/unresolved:** the 5-day gap-fill window and 20-day drift max-lag
are both reasonable, documented defaults, not deeply validated — real
measured shock frequency and behavior aren't known until this runs for
real. Also open: the shared shock-detection refactor with
`shock_clustering`, noted above as future cleanup.
