---
name: angle-30-trend_lifecycle
status: decided
purpose: discussion and enhancement proposal for the `trend_lifecycle` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/trend_lifecycle/`.
---

# 30 — trend_lifecycle

**Title (from spec.yaml):** Trend Lifecycle

## 1) Status

- Discussed: 2026-08-08
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py`,
  `peaks.py`, `snapshots.py`, `patterns.py`, `lifecycle.py`, `signals.py`
  at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/trend_lifecycle/`.
- Not a forecaster in the point/quantile sense — a self-accumulating
  peak/trough pattern library with KNN analog matching, rule-based
  lifecycle staging, and rule-based trade-signal generation. No
  `model_backend` question (no pretrained/trained-NN component at all —
  purely statistical feature matching plus hand-written rules).
- **Genuinely well-engineered in several places, verified directly, not
  assumed:**
  - Peak/trough detection uses an **ATR-adaptive threshold**
    (`effective_min_drop = min(fixed_floor_pct, -2×ATR%)`) — this
    codebase already independently arrived at the same volatility-
    normalized-threshold idea proposed for `drawdown_deep_dive` (angle
    06), which is a useful, real-world confirmation that the technique
    is sound and already proven out elsewhere in this project.
  - The KNN pattern matching (`find_similar`) is **correctly walk-forward
    safe** — every query only matches library rows with `bar_ts`
    strictly earlier than the query's own timestamp (`before_ts`
    filtering), so there's no lookahead leak in the matching itself.
  - The pattern library **genuinely accumulates** across runs (reads all
    prior mature snapshots from storage, deduplicates by `bar_ts`), not
    a stateless per-call computation.
- **Real gap found — the same "hand-tuned, unvalidated formula" pattern
  already caught and rejected once in this project.** `signals.py`'s
  confidence score (`confidence = min(0.95, 0.5 + high_conf*0.08 +
  avg_similarity*0.2)`) and exit-threshold formula
  (`exit_pct = abs(avg_dd) * 0.5`) are hardcoded constants with no stated
  derivation or historical validation — the same category of problem as
  `drawdown_deep_dive`'s original `news_driven_pct` formula
  (`weighted_score / (weighted_score + 0.1*n_events + 1.0)`), which was
  already identified and replaced with honest, validated output rather
  than a confidence-sounding invented number. This angle's signals
  currently make the same kind of unvalidated confidence claim.
- **Minor, confirmed config inconsistency**: both `_MIN_PEAK_DROP_PCT`
  and `_LOOKAHEAD_BARS` (internal dicts in `compute.py`/`snapshots.py`)
  already define a `"1W"` entry, but `spec.yaml`'s `time_formats` list
  omits `1W` entirely — the code was clearly built anticipating weekly
  support that was never actually exposed. Recommended fix: add `1W` to
  `spec.yaml`.
- Shared/common piece this depends on: [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md),
  applied to signal rows — see §5 for why the storage design here is
  otherwise self-contained, not the standard 3-layer pattern.

## 2) One-line definition

Trend Lifecycle watches for meaningful peaks and troughs in a stock's
price, remembers every one it's ever seen as a growing library, and when
a new peak forms, finds the 5 most similar historical peaks (by a
weighted mix of technical indicators) to estimate how far this one might
fall and suggest a concrete action — though right now its stated
confidence in that suggestion is a hand-picked formula, not something
checked against what actually happened historically.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Peak/trough detection | 20-bar lookback, 3-bar forward confirmation, ATR-adaptive minimum drop (code default, kept as-is) | already correctly volatility-adjusted — no change needed, unlike the original drawdown_deep_dive/regime_analysis/shock angles |
| Feature vector | 18 technical features (SMA ratios, RSI-14/7, ATR%, BB width%, volume ratio/z-score, runup/dip/relaxation bar counts, wick/body %, peak ratio, daily return, RSI divergence, ADX slope) — code default, kept as-is | a real, substantive technical-pattern feature set |
| Matching method | z-score-normalized cosine similarity, top-k=5, walk-forward safe via `before_ts` filtering, soft session-filter with `_MIN_SESSION_POOL=10` fallback (code default, kept as-is) | already correctly leak-free, no change needed |
| **Proposed: walk-forward signal-outcome backtest** | replay the already-leak-safe matching pipeline across history; for every historical `book_profits`/`hold`/`accumulate` signal that was actually generated, check what really happened afterward (was the suggested exit level a good stop, did "hold" during uptrend actually continue) | this is the real gap — currently nothing checks whether the system's own past suggestions would have worked, despite the matching plumbing needed to do so already existing |
| **Proposed: confidence calibration check** | bucket historical signals by their stated `confidence` score, compare each bucket's actual real-world hit rate against the stated confidence (a genuine calibration curve) | directly tests whether the hand-tuned formula's confidence numbers mean anything, instead of trusting them at face value |
| Confidence/exit-threshold formulas | **kept in the code as the live heuristic**, but their output is now labeled and evaluated as an unvalidated heuristic score until the calibration check (above) says otherwise | not rewritten blindly — replacing a formula with another guess wouldn't be an improvement; measuring it first is |
| Timeframes | 1min, 5min, 15min, 1H, 4H, 1D, 1W | **updated**: widened to the standard 6 plus the existing 1W (fixing the confirmed config gap — `1W` thresholds already exist in the code's own internal dicts, just weren't exposed in `spec.yaml`) — supersedes the earlier decision to deliberately exclude 1min/5min, which had argued peak/trough detection at 1-minute resolution would likely be dominated by tick-level noise |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |
| Data source | Alpaca | same as other angles |
| Symbol scope | parameterized — specific ticker or all tracked tickers | same as other angles |
| Time-based tagging | signal rows tagged per [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) (session/day/week/month/quarter for intraday timeframes; day/week/month/quarter only for 1D/1W) | applied to the new backtest's signal-outcome rows specifically — see §5 |

## 4) Example — what results look like

**Existing signal output (unchanged):**

```
signal_type: book_profits
confidence: 0.78
suggested_action: "Set trailing stop at -4.2% from peak ($148.20). Historical similar peaks dropped avg 8.4% (range: 3.1% to 15.7%)."
avg_drawdown_pct: -8.4
exit_threshold_pct: -4.2
lifecycle_stage: topping
n_high_confidence_matches: 4
```

**New: backtest evaluation of that same signal, once its outcome is
known:**

```
symbol: AAPL
signal_bar_ts: 2024-05-15T13:30:00Z
signal_type: book_profits
stated_confidence: 0.78
suggested_exit_pct: -4.2
actual_subsequent_drawdown_pct: -6.1
would_have_stopped_early: false
stop_would_have_helped: true
```

**New: confidence calibration curve (aggregate, the real point of this
enhancement):**

```
confidence_bucket: [0.7, 0.8)
n_signals: 34
actual_success_rate: 0.62
→ stated ~0.75 confidence, measured 62% success — real, useful gap to know about
```

(Illustrative — whether the formula turns out under- or over-confident
is a real, measured finding once this backtest runs, not assumed.)

## 5) Storage, querying, API shape

- **Existing (kept, unchanged)**: the pattern library itself is
  self-storing — every run reads all prior mature snapshots from
  `AngleStorage`, deduplicates by `bar_ts`, and the library grows. No new
  design needed for this part.
- **New: signal-outcome backtest table**: one row per historically
  generated signal, tagged per the shared time-slicing rule, carrying
  `stated_confidence`, `suggested_exit_pct`, and the real subsequent
  outcome once it's knowable (same "wait for the future to happen, then
  score it" pattern already used for `pnl_attribution`/`news_price_causality`).
- **New: confidence calibration aggregate**: precomputed buckets of
  stated confidence vs. measured success rate, each carrying `n` — same
  "always show sample size" discipline as everywhere else in this
  project.

This angle doesn't reuse the standard 3-layer forecast-row pattern
verbatim, because it isn't a per-candle forecaster — its existing
self-accumulating library is already its own well-suited storage design;
the addition here is a backtest/calibration layer on top, not a
replacement.

## 6) What we will achieve / how to use it

- An honest answer to whether this system's confidence scores and
  suggested exit levels are actually trustworthy, replacing blind trust
  in a hand-tuned formula with a measured calibration curve — the same
  kind of validation this project has already applied to
  `drawdown_deep_dive`'s attribution claim, `news_price_causality`'s
  significance model, and `peer_relative_strength`'s relative-return
  signal.
- If the calibration check shows the formula is reasonably well-behaved,
  that's a genuinely useful, positive finding — this isn't assumed to be
  broken, just unverified.
- A fixed, minor config gap (1W support) that the code was already built
  for but never exposed.
- Confirmation that the peak-detection and KNN-matching core is already
  sound — this angle's main real problem is the unvalidated confidence
  layer on top, not the underlying pattern-matching machinery.

## 7) Deeper rationale

**Why the confidence/exit formulas aren't simply rewritten with new
constants:** replacing one unvalidated guess (`0.5 + high_conf*0.08 +
avg_similarity*0.2`) with a different unvalidated guess wouldn't be
progress — it would just be a new, differently-shaped unverified claim.
Measuring the existing formula against real historical outcomes first is
what actually tells us whether it needs fixing, and if so, in which
direction — the same "measure before you fix" discipline used
implicitly throughout this project (e.g. ARIMA's compute-cost caveat
flagged as needing real benchmarking before a cadence decision).

**Why this is the same category of problem as `drawdown_deep_dive`'s
original attribution formula, not a new kind of finding:** both are
"looks reasonable, chosen without derivation or validation, presented
with false precision" constructions — a specific number like
`confidence: 0.78` invites more trust than a hand-tuned linear formula
with three arbitrary coefficients actually earns. Naming the parallel
explicitly is useful — it's the second time this exact failure mode has
shown up in this codebase, which is worth knowing if a third instance
turns up later.

**Why the backtest reuses the existing matching plumbing instead of
building something new:** the walk-forward-safe `before_ts` filtering
already exists and is already correct — replaying it across history to
score what past signals would have done is a natural extension of
infrastructure that's already there, not a new system.

**Why 1min/5min are deliberately not added:** peak/trough detection is a
structural, multi-bar-lookback concept — at 1-minute resolution, a
20-bar lookback covers only 20 minutes, well within normal intraday
noise, and would likely generate many spurious "peaks" that aren't
meaningful trend structure. This mirrors the same reasoning already
applied to keeping `shock_personality`'s gap detection at 1D-only.

**Open/unresolved:** whether the confidence formula turns out
well-calibrated, overconfident, or underconfident is a real, unknown
outcome of the proposed backtest — not guessed at here. The 1W spec.yaml
fix is a small, mechanical correction, not itself an open design
question.
