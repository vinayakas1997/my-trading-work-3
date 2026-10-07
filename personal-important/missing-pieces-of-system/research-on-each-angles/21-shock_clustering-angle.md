# 21 — shock_clustering

- **Angle id:** `shock_clustering`
- **Cluster:** C — Volatility & drawdown risk
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/shock_clustering/`
  (`compute.py`, `backtest.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Detects this ticker's own "shock" days (an unusual overnight gap or an
unusual intraday range, by rolling z-score) and reports which watchlist
peers tend to shock at the same time (co-shock rate, shock-day
correlation with a bootstrap CI). The module already fixed two real
bugs before this research (see F4) -- but a third, same-shaped issue
already found in two other angles (`peer_relative_strength`,
`regime_analysis`) is present here too, worse in this case because it
also breaks the "gap" concept itself, not just alignment (see F1-F3).

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | `open - prior_close` (as a fraction of prior close) is a meaningful "gap" signal -- a discrete jump between two observations, unexplained by anything that happened in between. | code's own design; economically this describes an **overnight** gap specifically |
| A2 | Overnight (close-to-open) price moves are a real, economically distinct phenomenon from moves that happen while the market is open, often linked to news/earnings landing outside trading hours. | [SC1] |
| A3 | Rolling (not whole-sample) z-score thresholds avoid the look-ahead leak already found and fixed in a sibling angle (`regime_analysis`). | code's own docstring |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Overnight vs. intraday returns, major indices and individual stocks, decades of data | "Overnight returns to major stock market indices over the past few decades have been wildly positive, while intraday returns have been disturbingly negative" -- described as "astonishingly consistent," a pattern strong enough that the two return components behave like genuinely different phenomena, not just noisier/cleaner versions of the same thing. | [SC1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | The anchor's own shocks (`_detect_shocks`) and returns (`_returns_by_date`) are computed from `bars`, fetched at whatever `time_format` was requested (1min through 1D per `spec.yaml`). Every **peer's** bars are always fetched with a hardcoded `interval="1D"`. | -- (internal, verifiable from the code alone) | **Same root-cause bug already found in `peer_relative_strength` (F1) and, differently, `regime_analysis` (F1) -- now a third instance.** At any non-`1D` `time_format`, the anchor's shock detection runs on intraday bars while every peer's runs on real daily bars -- two structurally different shock definitions being compared as if they were the same thing. |
| F2 | `_returns_by_date` keys its output dict by **calendar date** (`pd.Timestamp(ts, unit="s").normalize().date()`), and for intraday bars, later bars silently **overwrite** earlier ones sharing the same date (plain dict assignment, no aggregation). | -- (internal, verifiable) | **A second, distinct bug, worse than simple misalignment.** At `time_format="1min"`, `_returns_by_date` doesn't average or compound a day's ~390 bars into one daily return -- it keeps only whichever bar happened to be processed last for that date, discarding the other ~389. The `shock_day_correlation`/`co_shock_rate` computed from this is built on an arbitrary single-minute return standing in for "the day's return," not any real daily figure. |
| F3 | The "gap" shock trigger (`open - prior_close`) is computed identically regardless of `time_format`. | Overnight and intraday returns are documented as economically distinct, not interchangeable versions of the same signal [SC1]. | **A third, conceptually deeper issue on top of F1/F2.** For real daily bars, `open - prior_close` *is* the overnight gap -- a specific, meaningful "something happened while the market was closed" signal. For 1-minute bars, the same formula computes the difference between one minute's open and the *previous minute's* close -- routine intrabar microstructure noise, not an overnight gap at all. This isn't a miscalibrated threshold (like `regime_analysis`'s fixed percentage); it's the underlying concept itself only being coherent at daily-or-coarser granularity, silently reapplied to timeframes where "gap" means something else entirely. |
| F4 | The module's own docstring documents two bugs **already found and fixed** before this research: (1) a full-sample-constant gap trigger sitting next to an already-correct rolling-window range trigger -- fixed to use rolling everywhere; (2) the angle's original `dynamic_covariance` field reported an unconditional trailing correlation that never actually used the detected shock dates -- replaced with genuinely shock-conditional co-shock-rate and shock-day correlation, and the old, weaker, duplicate-of-`peer_relative_strength` metric was dropped rather than kept alongside. | -- | **Real, credited self-correction** -- both fixes are specific, verifiable, and match this research folder's own standards (look-ahead-leak awareness, not duplicating a weaker metric that already exists elsewhere in the codebase). |
| F5 | `shock_day_correlation`/`correlation_ci` are only reported when at least 5 paired shock-day observations exist; below that, both are `null` rather than a noisy number. Same for the whole-row `insufficient_shock_sample` status below `MIN_SHOCK_DATES=5`. | -- | Consistent with the same "never report a rate built on almost nothing" discipline already seen in `pnl_attribution`/`news_price_causality`. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `n_shock_dates` | How many of the anchor's own bars were classified as shocks. |
| `shock_dates` | Up to 10 most recent shock dates (string `YYYY-MM-DD`). |
| `cluster_members` | List of peers, sorted by descending `co_shock_rate`, each with: |
| &nbsp;&nbsp;`n_anchor_shock_dates` | Same as the row-level `n_shock_dates`, repeated per peer for convenience. |
| &nbsp;&nbsp;`n_co_shocked` | How many of the anchor's shock dates had a peer shock within ±1 day. |
| &nbsp;&nbsp;`co_shock_rate` | `n_co_shocked / n_anchor_shock_dates`. |
| &nbsp;&nbsp;`n_shock_day_pairs` | How many shock-date returns had both anchor and peer data (see F2 for a real limitation on what "a day's return" means at intraday timeframes). |
| &nbsp;&nbsp;`shock_day_correlation`, `correlation_ci` | Pearson correlation + bootstrap CI on the shock-date-restricted return pairs; `null` if fewer than 5 pairs. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Shock detection and peer comparison completed. | All fields above. |
| `no_data` | No bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (100 by default) bars. | + `n_observations`. |
| `insufficient_shock_sample` | Fewer than `MIN_SHOCK_DATES` (5) shocks detected for the anchor. | + `n_shock_dates`. |

## 7. Comprehensive explanation  *(for humans only)*

**What this angle already got right.** Unlike several angles researched
earlier in this folder, this one's own history (visible directly in its
docstring) shows two real bugs being found and properly fixed rather
than just documented: a look-ahead leak in the gap trigger (borrowing
the fix already validated in `regime_analysis`), and a metric that
didn't measure what its name promised (`dynamic_covariance` ignoring its
own detected shock dates entirely) -- replaced with a genuinely
shock-conditional pair of metrics, with the old, weaker, redundant
metric removed rather than left alongside as dead weight.

**The issue this research adds (F1-F3).** All three findings trace back
to one root cause already seen twice before in this folder
(`peer_relative_strength`, `regime_analysis`): the angle's constants and
data-fetching were designed and reasoned about purely in daily terms,
but `spec.yaml` declares it across 6 timeframes. Here the consequence is
sharper than in the other two angles, because "gap" isn't just a
miscalibrated threshold -- it's a concept (the overnight close-to-open
move) that is specifically and only meaningful across a session
boundary. Documented research on overnight vs. intraday returns treats
them as genuinely different phenomena, not the same signal at different
resolutions [SC1]; recomputing "gap" between consecutive 1-minute bars
doesn't just use the wrong window size, it measures something else
entirely. Combined with F2's date-key overwriting (which silently
discards all but one bar per day at intraday granularity) and F1's
anchor/peer granularity mismatch, every non-`1D` run of this angle is
comparing an intraday-derived, single-bar-per-day-sampled anchor signal
against a genuinely daily peer signal -- three compounding problems, not
one.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| SC1 | Bruce Knuteson, "Strikingly Suspicious Overnight and Intraday Returns," arXiv:2010.01727 (abstract) | Overnight and intraday returns to major stock indices documented as behaving as economically distinct, "astonishingly consistent" phenomena over decades -- used here to support that a "gap" (close-to-open) signal is conceptually specific to session boundaries, not a scale-free measure of "unusual price movement" applicable identically at any bar resolution. | https://arxiv.org/abs/2010.01727 |
| -- | Direct trace of `vinu_initial_analysis/runner.py`'s `_fetch_bars` (per-`time_format` fetch for the anchor) against `angles/shock_clustering/compute.py`'s peer fetch (`interval="1D"` hardcoded) and `_returns_by_date`'s date-keyed dict (silent overwrite on same-date collisions) | Confirmed the anchor/peer granularity mismatch (F1) and the intraday-return-discarding date-key collision (F2). | (local code read, 2026-09-24) |
