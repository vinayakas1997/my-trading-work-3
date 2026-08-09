---
name: angle-24-shock_clustering
status: decided
purpose: discussion and enhancement proposal for the `shock_clustering` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/shock_clustering/`.
---

# 24 — shock_clustering

**Title (from spec.yaml):** Shock Clustering

## 1) Status

- Discussed: 2026-08-08
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/shock_clustering/`,
  cross-checked against the shared
  `vinu_tools/compute/risk/covariance.py` (`dynamic_covariance`,
  `correlation_from_covariance`) it calls into.
- Not a forecaster, not a pretrained/fallback situation — event
  detection (shock dates) plus a cross-symbol co-movement check.
- **Confirmed bug #1 — same leak class as `regime_analysis`'s fix.** The
  gap-based shock trigger computes `gap_mean = gaps.mean()` /
  `gap_std = gaps.std()` over the **entire** bars series, a full-history
  constant — right next to the intraday-range trigger, which correctly
  uses a rolling `.rolling(21)` window. Same defect, same fix (make it
  rolling too) — see §7.
- **Confirmed bug #2 — the spec's core claim doesn't match what the code
  does, verified by reading the shared function it calls.** `spec.yaml`
  states the angle reports *"dynamic covariance sampled specifically at
  shock dates."* Read `vinu_tools/compute/risk/covariance.py`'s
  `dynamic_covariance()` directly: it takes `recent =
  log_returns[:, -window:]` — an **unconditional trailing 63-day
  window**, with no awareness of which days were shocks at all. The
  `shock_dates` list computed in this angle is only used for reporting
  (`n_shock_dates`, first 10 dates) — it never filters or conditions the
  correlation calculation. The angle currently reports a generic
  recent-63-day correlation that has nothing to do with shocks,
  contradicting its own name and spec. `spec.yaml` also promises
  "confidence intervals" that the code never computes at all. Same
  pattern already caught in `backtesting_44_metrics` (44 claimed vs. 18
  real) and `pnl_attribution` ("attribution" claimed, plain aggregate
  delivered).
- **Decision: make the angle actually shock-conditional, and drop the
  generic correlation it currently substitutes for that.**
  `peer_relative_strength` (angle 21) already covers general rolling
  correlation between a symbol and its watchlist peers — keeping a
  second, less rigorous, unconditional correlation here would be
  redundant with that angle, not a genuine "shock clustering" signal.
  See §3/§7.
- **Same honest limitation as `peer_relative_strength`/`moirai`**: the
  comparison universe is the caller's watchlist, not a curated peer
  group. Not fixed here, same reasoning as angle 21.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md),
  applied to shock-date rows — see §5.

## 2) One-line definition

Shock Clustering finds a stock's genuinely unusual single-day moves
("shocks" — bigger overnight gaps or intraday ranges than that stock's
own recent normal), then checks which of its watchlist peers actually
tended to shock *around the same time*, and how strongly their returns
moved together specifically on those shock days — not just how
correlated they are on an average day.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Shock detection — gap trigger | `abs(gap_z) > 2.0`, **fixed to use a rolling window** (`gap_mean`/`gap_std` via `.rolling(21)`, matching the intraday-range trigger right next to it) instead of the full-sample constant | closes confirmed bug #1 — same leak class, same fix already applied to `regime_analysis` |
| Shock detection — intraday-range trigger | `vol_z > 2.0` on `(high-low)/close`, rolling 21-day mean/std (code default, kept as-is) | already correct in the code, no change needed |
| **Core redesign: shock-conditional co-movement, not generic correlation** | for each peer, compute (1) **co-shock rate** — the fraction of the anchor's shock dates where that peer *also* independently registered as shocked (its own gap/range triggers, ±1 trading day window) — and (2) **shock-day correlation** — Pearson correlation of returns, computed only on the anchor's shock-date subset, with a bootstrapped 95% CI | replaces the generic, unconditional `dynamic_covariance`-based correlation the code currently reports — this is what actually answers "do these symbols shock together," which the current code doesn't measure at all |
| Co-shock window | ±1 trading day (peer's own shock date within 1 day of the anchor's) | shocks from a shared cause (e.g. a macro event) don't always land on the exact same calendar day across tickers due to timing/reporting differences; a same-day-only rule would undercount real co-shocks. Not deeply validated — a documented, reasonable default, open to a future robustness sweep (0/1/2 days) similar in spirit to angle 06's k-sweep |
| Shock-day correlation method | reuses `news_price_causality/correlation.py`'s existing bootstrap-CI Pearson approach directly | not a new statistical technique — the same already-validated method, applied to a shock-filtered return series instead of the news/return series it was built for |
| Dropped: generic `dynamic_covariance`-based correlation | removed from this angle's output entirely | redundant with `peer_relative_strength` (angle 21), which already covers general rolling correlation; keeping a second, less rigorous version here would just create the same "two divergent definitions" problem already fixed in `regime_analysis` |
| Peer universe | watchlist-derived (code's real behavior, kept as-is) | same honest limitation as `peer_relative_strength`/`moirai` — not fixed here |
| Min observations | 100 candles (floor for the rolling shock-detection windows to stabilize) | separate, real gating factor: even with enough candles, a symbol may simply not have enough *detected shock dates* for co-shock-rate/correlation to be meaningful — see thin-sample handling below |
| Thin-sample handling | if fewer than 5 shock dates are detected for the anchor over the requested range, status is `insufficient_shock_sample`, no co-shock/correlation stats computed | same "don't report a rate built on almost nothing" discipline as `pnl_attribution`/`news_price_causality` |
| Timeframe | 1min, 5min, 15min, 1H, 4H, 1D | **updated**: widened to the standard 6, same as every other angle — supersedes the earlier 1D-only decision, which had argued shock detection (overnight gaps, daily range) is inherently a daily-bar concept |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca (symbol + watchlist peers) | same as other angles |
| Symbol scope | parameterized — specific ticker, peers from that call's watchlist | matches code's real interface |
| Time-based tagging | shock-date rows tagged by their own date: day-of-week/week/month/quarter, no session (daily granularity, same reasoning as `peer_relative_strength`/`regime_analysis`) | shared rule, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |

## 4) Example — what results look like

**Per-shock-date row (new, tagged):**

```
symbol: AAPL
date: 2024-05-14
trigger: gap
gap_z: 2.34
+ day_of_week: Tuesday
+ week_of_month: 2
+ month: May
+ quarter: Q2
```

**Per-peer co-movement summary (replaces the old generic correlation):**

```
symbol: AAPL
peer_symbol: MSFT
n_anchor_shock_dates: 14
n_co_shocked: 9
co_shock_rate: 0.64
shock_day_correlation: 0.58
correlation_ci: [0.21, 0.79]
n_shock_day_pairs: 14
status: ok
```

**Thin-sample case (honestly reported, not silently computed anyway):**

```
symbol: XOM
peer_symbol: CVX
n_anchor_shock_dates: 3
status: insufficient_shock_sample
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows**: one row per detected shock date for the
  anchor symbol, tagged per
  [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md).
- **Layer 2 — precomputed common keys**: per-(symbol, peer) co-shock
  rate and shock-day correlation, each carrying its own `n` (both
  `n_anchor_shock_dates` and the correlation sample size).
- **Layer 3 — on-demand query service**: same shared pattern as other
  angles, e.g. "co-shock rate for this pair in Q2 2024 only" composed
  from Layer 1 shock-date rows.

## 6) What we will achieve / how to use it

- An answer to the question the angle's name actually asks — "which
  symbols shock together" — that the current code doesn't measure at
  all (it reports an unrelated generic correlation instead).
- Delivers the confidence intervals `spec.yaml` already promised but the
  code never computed, using an already-validated technique instead of
  inventing a new one.
- A genuinely distinct signal from `peer_relative_strength` instead of a
  redundant, less rigorous overlap — that angle answers "how correlated
  are these stocks generally," this one answers "do they specifically
  move together during unusual events."
- Honest handling of thin samples (`insufficient_shock_sample`) instead
  of silently reporting a co-shock rate built on 2-3 data points as if
  it meant something.

## 7) Deeper rationale

**Why the gap-trigger leak gets the same fix as `regime_analysis`,
without re-deriving it from scratch:** it's the identical defect
category (a full-sample constant used to judge whether a specific
earlier point was unusual) that was just diagnosed and fixed one angle
ago — applying the same rolling-window treatment here is consistency,
not a new decision.

**Why the generic correlation is dropped instead of kept alongside the
new shock-conditional metrics:** the whole point of this angle, per its
own name and spec, is shock-specific co-movement. Keeping the generic
`dynamic_covariance` correlation as well would mean this angle
duplicates `peer_relative_strength`'s job using a strictly weaker method
(a single unconditional snapshot, no CI) alongside its own real,
shock-conditional numbers — confusing which correlation value a
downstream consumer should actually trust. One rigorous, on-topic metric
beats one rigorous metric plus one redundant, off-topic one.

**Why co-shock rate is the primary metric, not just correlation:** "do
these symbols shock together" is most directly answered by a literal
co-occurrence rate — did the peer also have its own unusual day near the
anchor's. Correlation on shock days is a real, useful secondary measure
of *how strongly* returns moved together when they did co-occur, but the
co-occurrence question itself is what the angle's name promises, and a
correlation coefficient alone doesn't directly answer it.

**Why ±1 trading day for co-shock matching, not same-day only:** shocks
driven by a shared cause (e.g. a macro announcement, sector-wide news)
don't always register on the exact same calendar bar across tickers —
premarket/afterhours timing and each stock's own gap-vs-intraday-range
trigger can shift which single day it's flagged on by one session. A
same-day-only rule would likely undercount genuine co-shocks. This is a
judgment call, documented rather than hidden, and flagged as open to a
future robustness sweep the same way angle 06 sweeps `k`.

**Why the shock-day correlation reuses `correlation.py`'s exact bootstrap
method instead of `dynamic_covariance`:** `dynamic_covariance` has no way
to condition on an arbitrary date subset — it always takes the trailing
N periods, unconditionally. Since the design need is "correlation
computed only on these specific (shock) dates," the already-validated
bootstrap-Pearson approach (built for exactly this kind of filtered,
CI-aware correlation in `news_price_causality`) is the right tool, not
the shared covariance utility this angle currently misuses.

**Open/unresolved:** the ±1-day co-shock window and the 5-shock-date
thin-sample floor are both reasonable, documented defaults, not deeply
validated — real measured shock frequency (how many shock dates a
typical watchlist symbol actually accumulates over the date range) isn't
known until this runs for real, and could motivate revisiting either
number.
