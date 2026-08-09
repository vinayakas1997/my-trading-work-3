---
name: angle-23-regime_analysis
status: decided
purpose: discussion and enhancement proposal for the `regime_analysis` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/regime_analysis/`.
---

# 23 — regime_analysis

**Title (from spec.yaml):** Regime Analysis

## 1) Status

- Discussed: 2026-08-07
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/regime_analysis/`,
  cross-checked against `news_price_causality/regime_features.py` and
  `signal_contract.py`.
- Not a forecaster, not a pretrained/fallback situation — classical
  rolling-window regime bucketing (bull/bear/high_vol/sideways) plus a
  regime-transition count summary.
- **A confirmed, cross-referenced bug — not a new suspicion, already
  caught and worked around elsewhere in this codebase, just never fixed
  at the source.** `classify_regime`'s volatility threshold
  (`vol.quantile(0.7)`) is computed over the **entire sample series** —
  a full-history constant. Three independent pieces of evidence confirm
  this is real and already known:
  1. The math itself: a threshold computed from the whole date range
     necessarily uses future data to label an earlier bar's regime.
  2. `news_price_causality/regime_features.py`'s own module docstring
     names this exact defect by name: *"the stored `regime_analysis`
     angle's `classify_regime` buckets volatility against
     `vol.quantile(0.7)` computed over the ENTIRE sample series... if a
     news article itself caused the high-vol spike... the stored label
     would already embed the post-event move... a fresh leak."* That
     module was built specifically to route around this angle's own
     leak, rather than fix it here.
  3. `signal_contract.py`'s `SIGNAL_USAGE_CONTRACT` registry explicitly
     restricts the `regime_feature` tag to `["volatility_bucketing",
     "regime_labeling"]` and marks `["direction_prediction",
     "forward_return_prediction"]` as **not proven** — citing
     `regime_features.py` as the evidence.
- **Decision: adopt the already-validated fix, not a new one.**
  `regime_features.py` already solved this correctly (rolling/trailing
  vol z-score against a 120-day baseline, computed strictly up to each
  point in time). This angle's design consolidates onto that exact same
  method rather than maintaining two divergent regime definitions in the
  same codebase.
- **This angle's output stays within the existing signal-usage
  boundary**: descriptive/diagnostic (which regime a period was, how
  regimes historically sequence) — not a claim that regime labels predict
  direction or forward returns. That boundary was already decided
  elsewhere (`signal_contract.py`); this design respects it rather than
  re-litigating it.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md),
  applied to a new per-bar layer this design adds — see §5.

## 2) One-line definition

Regime Analysis labels every trading period as bull, bear, high-volatility,
or sideways based on its recent return and volatility, then reports how
each regime type historically performed and how often the market shifts
from one regime into another — using a corrected, leak-free version of a
volatility threshold this codebase already knew was broken.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Regime categories | bull / bear / high_vol / sideways, `high_vol` takes priority over bull/bear when both conditions are true | kept from code, matches both the original and the already-validated `regime_features.py` version — a high-vol bull rally gets labeled `high_vol`, not `bull`, by design in both existing implementations |
| Realized vol window | 21-period rolling std, annualized via `ann_factor(time_format)` | kept from code, matches both existing implementations |
| **Vol threshold — fixed** | replaces the leaky full-sample `vol.quantile(0.7)` with a rolling z-score: `(21d vol − 120d trailing mean of 21d vol) / 120d trailing std`, `high_vol` if `z > 1.0` | **directly adopts `regime_features.py`'s already-validated formula** — not a new invention, just applying an existing, proven fix to the angle that actually needed it |
| **Return measure for bull/bear — changed** | 20-period cumulative relative return (`close.pct_change(20)`) instead of the original single-period `pct_change()` | matches `regime_features.py`'s `rel_days=20` — smoother, less noisy regime signal than a single-bar return; consolidates the two existing divergent definitions into one |
| Bull/bear threshold | kept at fixed ±1% (inherited from both existing implementations) | **known, flagged limitation, not fixed in this pass** — ±1% doesn't mean the same thing on 1D vs. 1W vs. 1M bars; a natural future extension of the volatility-adaptive threshold idea already applied to `drawdown_deep_dive` (angle 06), deliberately not invented here to avoid unscoped scope creep in the same pass as the leak fix — see §7 |
| Min observations | 141 periods (120-day trailing baseline + 21-day vol window) | a real, derived floor for the corrected method — not the arbitrary N=100 convention, tied directly to what the z-score calculation actually requires |
| Timeframes | 1min, 5min, 15min, 1H, 4H, 1D, 1W, 1M | **updated**: widened to the standard 6 plus the two existing coarser timeframes kept (1W, 1M), same union approach as `backtesting_44_metrics` — supersedes the earlier 1D/1W/1M-only decision, which had argued regime is conventionally a slower, multi-day phenomenon not meant for intraday extension |
| **New: per-bar tagged rows** | in addition to the existing whole-history-per-regime summary, also emit one row per classified bar, tagged day-of-week/week/month/quarter | closes a real gap — the current code only ever outputs one aggregated row per regime across the *entire* requested date range, so "was Q1 2023 mostly bull or bear" isn't answerable today; same two-granularity pattern already used for `news_price_causality` (per-event rows + coarser aggregate) |
| Transition matrix — normalized | add `transition_prob` (`count / total transitions FROM that regime`) alongside the existing raw `count`, always paired with `n` | raw counts alone force every consumer to normalize manually; matches the project-wide "never present a rate without its sample size" discipline used everywhere else |
| Signal usage contract | unchanged — `regime_feature` stays `proven_for: [volatility_bucketing, regime_labeling]`, `not_proven_for: [direction_prediction, forward_return_prediction]` | already correctly decided in `signal_contract.py`; cited here, not re-decided |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |

## 4) Example — what results look like

**New: per-bar tagged row (Layer 1):**

```
symbol: AAPL
timeframe: 1D
bar_ts: 2024-05-15T13:30:00Z
regime: bull
ret_20d: 0.034
vol_21d: 0.21
vol_trailing_z: 0.42
+ day_of_week: Wednesday
+ week_of_month: 3
+ month: May
+ quarter: Q2
```

**Existing (kept): whole-history-per-regime summary:**

```
symbol: AAPL
metric: regime_stats
regime: bull
count: 312
total_return: 0.487
avg_return: 0.0016
sharpe: 1.42
win_rate: 0.61
pct_of_time: 0.34
```

**New: per-quarter regime breakdown (closes the current gap):**

```
symbol: AAPL
quarter: 2024-Q2
regime: bull
count: 41
pct_of_time_in_quarter: 0.68
```

**Transition matrix, now with normalized probability:**

```
regime_from: bull
regime_to: high_vol
count: 14
n_from_bull: 312
transition_prob: 0.045
```

## 5) Storage, querying, API shape

- **Layer 1 — raw tagged rows (new)**: one row per classified bar,
  tagged per [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)
  (day-of-week/week/month/quarter — no session/subsession, same reasoning
  as `peer_relative_strength`: this is daily+ granularity, not intraday).
- **Layer 2 — precomputed common keys**: both the existing whole-history-
  per-regime summary (kept, unchanged shape) and a new per-(symbol,
  quarter, regime) breakdown, each carrying `n`.
- **Layer 3 — on-demand query service**: same shared service as every
  other angle, composes custom slices (e.g. per-month instead of
  per-quarter) from Layer 1 on demand.
- **Transition matrix**: stored as its own small table, `count` +
  `n_from_<regime>` + `transition_prob` per (from, to) pair — an
  aggregate by construction, same "never a raw per-row field" treatment
  as RMSE/pinball loss in the forecasting angles.

## 6) What we will achieve / how to use it

- A regime classification that's actually leak-free, closing a bug this
  codebase already knew about (via `regime_features.py`'s own docstring
  and `signal_contract.py`'s restriction) but had only worked around
  downstream, never fixed at the source.
- Time-sliced regime visibility that doesn't exist today — "which
  quarters were bull-dominated," not just "34% of the whole 4.5-year
  range was bull."
- A genuinely usable transition matrix (normalized probabilities, not
  just raw counts) — a real Markov-style view of "given we're in regime
  X, what's the actual probability of moving to regime Y next," always
  paired with its own sample size.
- Consolidates two currently-divergent regime definitions (the original
  angle's leaky, single-period-return version, and `regime_features.py`'s
  correct, point-in-time-safe version) into one, so future consumers
  don't have to guess which one is trustworthy.
- Stays honestly within the already-decided signal-usage boundary — this
  is a labeling/description tool, not a claim of predictive power over
  direction or forward returns.

## 7) Deeper rationale

**Why this leak bug gets a definite fix, not just a flag:** unlike some
open items elsewhere in this project that are genuinely unresolved
judgment calls, this one already has a validated, working fix sitting in
the same codebase (`regime_features.py`), independently confirmed by a
second source (`signal_contract.py`'s restriction, which exists
*because* of this exact leak). Leaving the original angle broken while a
correct version exists three files away isn't an open question, it's
just unfinished cleanup — closing it here consolidates the codebase onto
one correct definition instead of two disagreeing ones.

**Why adopt `regime_features.py`'s exact formula instead of designing a
new one:** that module's approach (120-day trailing baseline, z-score
rather than a quantile, 20-day cumulative return rather than single-bar)
is already validated — it's the version `significance_model.py` actually
trusts enough to use as classifier input. Inventing a third variant here
would recreate the exact problem being fixed: multiple regime
definitions floating around with no clear "which one is right" answer.

**Why the ±1% bull/bear threshold is flagged, not fixed, in this same
pass:** it's a real, known limitation — same class of problem as the
fixed -2% drawdown threshold before angle 06 added `k × ATR%` — but
fixing it here would mean inventing a second new methodology in the same
discussion as fixing a confirmed leak bug, conflating a definite
correctness fix with a genuinely open design choice. Better to land the
leak fix cleanly now and treat the threshold-scaling question as its own
follow-up, consistent with how this project separates "this is broken,
fix it" from "this is a judgment call, flag it."

**Why per-bar tagged rows are added alongside the existing whole-history
summary, not instead of it:** the whole-history summary is still useful
(a fast, always-available "how has this regime behaved overall"
answer). But it can't answer time-sliced questions at all today. Adding
the finer per-bar layer — same two-granularity pattern already
established for `news_price_causality` — gets both without discarding
what already works.

**Why transition probabilities are normalized, not left as raw counts:**
raw counts require every consumer to independently figure out the
right denominator (total transitions *from* that specific regime, not
total transitions overall) — an easy place to get a "probability" subtly
wrong. Normalizing once, centrally, with `n` always attached, removes
that risk and matches how every other rate/probability in this project
is already handled.

**Open/unresolved:** the ±1% bull/bear threshold's timeframe-scaling
issue (flagged above, not fixed here) is the main open item. Also open:
whether the transition matrix should itself eventually be time-sliced
(e.g. "regime transition probabilities during Q2 2024 specifically")
the same way the regime_stats summary now is — not proposed here, since
transition counts need a larger sample to be meaningful than a single
quarter would likely provide, but worth revisiting once real data volume
is known.
