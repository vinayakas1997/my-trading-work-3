# 22 — shock_personality

- **Angle id:** `shock_personality`
- **Cluster:** C — Volatility & drawdown risk
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/shock_personality/`
  (`compute.py`, `backtest.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Characterizes how this ticker *behaves* after its own shocks: how much
of a gap gets filled in the following 5 bars, how persistent its
volatility regime is (real GARCH, reusing the same `garch_volatility`
already researched in [07-garch-angle.md](07-garch-angle.md)), and how
long/correlated the post-shock drift is -- each split by whether news
was nearby. **Three real bugs were found and fixed before this
research** (see F1), the most of any angle in this folder so far. One
issue remains, shared with `shock_clustering`: the "gap" concept and
every fixed-bar window here assume daily bars (see F2).

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Gap and volatility shocks should use **rolling** (point-in-time) thresholds, not a whole-sample constant, so the same computation works identically in a backtest and in live production. | code's own docstring, same fix already validated in `regime_analysis`/`shock_clustering` |
| A2 | Post-shock return **autocorrelation**, not just a sign-streak, is informative about drift persistence, and should be reported, not silently computed and discarded. | code's own docstring (Bug #2) |
| A3 | `open - prior_close` measures an **overnight** gap specifically -- see [21-shock_clustering-angle.md](21-shock_clustering-angle.md) A2/F3 for the literature on overnight vs. intraday returns being economically distinct, which applies identically here. | [SC1] (already opened for that file) |

## 3. Assumption results  *(passed to the LLM)*

Not applicable in the disputed-literature sense -- this angle's fixes
are internal corrections, not claims from external sources. See
`shock_clustering`'s R1 for the overnight-vs-intraday evidence this
angle's "gap" concept also depends on.

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Module docstring documents **three** bugs found and fixed here: (1) the gap-shock trigger's mean/std were a full-sample constant next to an already-correct rolling vol-spike trigger -- fixed to rolling(21), independently duplicating the same fix already made in `shock_clustering` rather than sharing code; (2) post-shock return autocorrelation was computed per shock but only checked for non-NaN, the actual numbers thrown away -- now aggregated and reported as `drift_mean_autocorr`; (3) per-shock `has_news`/`nearest_news_days` tags were computed but never reached the output, only an aggregate `n_shocks` count did -- now surfaced and used to split every other metric by news presence. | -- | **The most self-corrected angle researched so far** -- three specific, verifiable "computed, then discarded" or "leaked" bugs, each fixed with a clear before/after described in the code's own comments. Bug #1 being independently reimplemented rather than sharing `shock_clustering`'s fix is a minor missed reuse opportunity, not a correctness issue. |
| F2 | `GAP_ROLLING_WINDOW=21`, `VOL_ROLLING_WINDOW=21`, `fill_window=5` (bars until gap-fill is checked), `max_lag=20` (bars of post-shock drift examined) are all bar counts, applied unchanged across the 6 declared `time_formats` (1min-1D); the gap trigger itself (`open - prior_close`) is the same overnight-specific formula regardless of bar granularity. | Overnight and intraday returns are economically distinct, documented phenomena, not interchangeable at different resolutions [SC1]. | **The same systemic issue now confirmed in a fourth angle** (`peer_relative_strength`, `regime_analysis`, `shock_clustering`, and this one). At `1min`, `fill_window=5` checks whether a gap "filled" within 5 minutes rather than several sessions, and `open - prior_close` measures intrabar microstructure noise, not an overnight gap, for exactly the reasons already established in `shock_clustering`. Unlike `shock_clustering`, this angle has no cross-symbol peer-fetch step, so it avoids that specific sub-bug -- but the core gap-concept and window-sizing issues are identical. |
| F3 | `gap_fill_rate` is a continuous value clipped to `[0, 1]` (not a true binary proportion), averaged with `mean_with_ci`'s Student's-t interval. | Wald/t-style intervals are specifically documented as problematic for **binomial proportions** (0/1 data), per [19-pnl_attribution-angle.md](19-pnl_attribution-angle.md)'s citation. | Milder than `pnl_attribution`'s `win_rate` case -- `gap_fill_rate` is a bounded continuous quantity, not 0/1 data, so a t-interval is a more defensible choice here, though it can still in principle extend past `[0, 1]` at small n. Not flagged as a confirmed bug, just a lighter version of the same general caveat. |
| F4 | `_compute_vol_persistence` hardcodes `time_format="1D"` in its call to the shared `garch_volatility`. | Traced against `garch_volatility`'s own source (already read for [07-garch-angle.md](07-garch-angle.md)): the `time_format`/annualization-factor argument only affects the returned `conditional_vol` series, never the `alpha`/`beta`/`omega` values this function actually uses. | **Not a bug** -- verified directly: since only `alpha`/`beta`/`omega` are consumed here (not `conditional_vol`), the hardcoded `"1D"` is inert regardless of the bars' real granularity. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `n_shocks`, `n_shocks_with_news` | Total detected shocks (gap + vol-spike, de-duplicated by date), and how many had news within ±2 days. |
| `gap_fill_rate`, `gap_fill_rate_news`, `gap_fill_rate_no_news` | `{mean, n_observations, confidence_interval, status}` -- how much of a gap closed within 5 bars, overall and split by news presence. |
| `vol_persistence` | `{alpha, beta, omega, persistence, status}` from a real GARCH(1,1) fit (see F4) -- `persistence = alpha + beta`, same meaning as in [07-garch-angle.md](07-garch-angle.md). |
| `drift_persistence_days` (+ `_news`/`_no_news`) | `{mean_days, n_observations, confidence_interval, status}` -- mean length of the sign-streak following a shock before the first reversal. |
| `drift_mean_autocorr` | `{mean, n_observations, confidence_interval, status}` -- mean lag-1-through-9 return autocorrelation following shocks (previously computed and discarded -- Bug #2). |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Shock detection and metrics computed (individual sub-metrics may still be `insufficient_sample` internally). | All fields above. |
| `no_data` | No bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (21 by default -- the rolling windows' own floor, not the shared 100-bar convention) bars. | + `n_observations`. |

Each nested `{mean, n_observations, confidence_interval, status}` block
carries its own `insufficient_sample` (n < 2) independently of the
row-level `status`.

## 7. Comprehensive explanation  *(for humans only)*

**Why this is the most self-corrected angle in this folder.** Three
separate categories of real bug, each with a distinct signature (a
statistical leak, a computed-then-discarded metric, and a
computed-then-unreported per-item tag), all documented with a clear
before/after in the module's own comments. That's a stronger track
record than any other angle researched so far, including the otherwise
very careful `news_price_causality` and `kalman_filters`.

**The one issue this research adds (F2).** It's the fourth confirmed
instance of a pattern this folder has now established clearly across
`peer_relative_strength`, `regime_analysis`, `shock_clustering`, and
this angle: fixed bar-counted windows and an overnight-specific "gap"
formula, all reasoned about in daily terms, applied unchanged across a
`time_formats` list spanning minutes to a full day. Given how
consistently this same root cause recurs, it looks less like four
independent oversights and more like a shared, unaddressed gap in how
non-daily timeframes were handled when several of Cluster C's angles
were built or later widened to declare intraday support.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| SC1 | (Already opened and cited in [21-shock_clustering-angle.md](21-shock_clustering-angle.md)) Bruce Knuteson, "Strikingly Suspicious Overnight and Intraday Returns," arXiv:2010.01727 | Reused finding: overnight and intraday returns are documented as economically distinct phenomena, supporting why this angle's "gap" concept (also `open - prior_close`) is specifically an overnight-scale signal, not resolution-independent. | https://arxiv.org/abs/2010.01727 |
| -- | Direct read of `vinu_tools/compute/risk/volatility.py`'s `garch_volatility` (already read in full for [07-garch-angle.md](07-garch-angle.md)) | Confirmed `time_format` only affects the returned `conditional_vol` series, not `alpha`/`beta`/`omega` -- used to rule out F4 as a bug. | (local code read, 2026-09-24, reused from prior research) |
