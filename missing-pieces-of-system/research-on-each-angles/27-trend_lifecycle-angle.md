# 27 — trend_lifecycle

- **Angle id:** `trend_lifecycle`
- **Cluster:** F — Pattern history & lifecycle
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/trend_lifecycle/`
  (`compute.py` orchestrator + `peaks.py`, `snapshots.py`, `patterns.py`,
  `lifecycle.py`, `signals.py`, `compile_dashboard.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Detects this ticker's own price peaks/troughs, snapshots each one's
indicator profile, matches new peaks against a growing historical
library via KNN, classifies the current lifecycle stage (uptrend /
downtrend / topping / basing / sideways, from higher-highs/higher-lows
logic), and emits reversal signals. Glossary already calls this a "real,
load-bearing angle." **The peak-detection threshold table is missing
entries for two of its seven declared timeframes** (see F1) -- a real,
confirmed gap, not a design choice.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | A systematic, automatic approach to detecting local price extrema and comparing return distributions conditioned on the resulting patterns can measure whether "charting"-style technical patterns carry real incremental information. | [TL1] |
| A2 | Peak/trough matching must be **walk-forward safe** -- a query peak should only ever be compared against historical peaks with a strictly earlier timestamp, never a peak from the future relative to the query. | code's own design (`before_ts` filter in `find_similar`) |
| A3 | A peak-drop threshold should scale with the ticker's own recent volatility (via ATR), not stay flat regardless of how calm or volatile the stock currently is. | code's own design (the `atr_adj`/`effective_min_drop` mechanism) |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Kernel-regression-identified technical patterns (head-and-shoulders, double-tops/bottoms, etc.), U.S. stocks, 1962-1996 | "Over the 31-year sample period, several technical indicators do provide incremental information and may have some practical value" -- a real, but modest and hedged, finding, not a strong endorsement of technical charting generally. | [TL1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `_MIN_PEAK_DROP_PCT` has entries for `15min`/`1H`/`4H`/`1D`/`1W` only. `spec.yaml` declares this angle across **7** timeframes, including `1min` and `5min`. `.get(tf, -3.0)` means both missing timeframes silently fall back to the **1H** default. | -- (internal, verifiable from the code alone) | **Real, confirmed gap.** A -3% drop is already a large move at 1-hour resolution; requiring the same -3% at 1-minute resolution means a "peak" essentially never registers, since most stocks rarely move 3% within a single minute-scale window. This is the same general category of issue found repeatedly elsewhere in this codebase (fixed thresholds not adapted per declared timeframe) -- but here it's specifically a *missing dictionary entry*, not a miscalibrated constant applied everywhere. |
| F2 | The ATR-based adjustment (`effective_min_drop = min(min_drop, -atr_adj)`) is meant to scale the threshold to the ticker's actual volatility. | -- (internal, verifiable from the code alone) | **Does not rescue F1.** Both `min_drop` and `-atr_adj` are negative; `min()` of two negative numbers picks whichever has the *larger magnitude* -- so this mechanism can only make the effective threshold **stricter** (when the ticker's ATR-implied move is unusually large), never **looser** (when it's naturally small, as at 1-minute resolution). For 1min/5min bars, the ATR-implied percentage will almost always be smaller in magnitude than -3.0%, so `min()` keeps -3.0% unchanged -- the ATR adjustment doesn't compensate for the missing per-timeframe entries at all. |
| F3 | `find_similar` is called with `before_ts=snap.get("bar_ts")` for every query, and the match pool excludes rows whose `outcome_mature` flag is explicitly `False` (provisional, not-yet-finalized outcomes). | -- | **A real, deliberate look-ahead-safety design**, in the same spirit as `kalman_filters`' filtered/smoothed separation and `regime_analysis`'s rolling-baseline fix -- worth crediting as a positive, verified-by-reading pattern rather than assumed. |
| F4 | Lifecycle stage classification (`uptrend`/`downtrend`/`topping`/`basing`) is derived purely from whether recent peaks and recent troughs are each trending higher or lower -- the classical "higher highs, higher lows" definition of trend. | Not separately researched here as a distinct citation -- this is standard, long-established charting convention (Dow's trend definition), not a disputed claim requiring its own literature check the way an ML architecture's fidelity does. | Reasonable, conventional logic; no external claim to verify beyond what [TL1] already establishes about extrema-based technical analysis in general. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

Multiple row `type`s in one run:

| `type` | Meaning |
|---|---|
| `snapshot` | One row per newly-detected peak/trough, with its indicator profile at that point (`inflection_type: "peak"`/`"trough"`, `outcome_mature` flag). |
| (match rows, untyped in this excerpt) | One row per KNN match for a query peak: `query_bar_ts`, `similarity`, `matched_drawdown_pct`, etc. |
| (lifecycle row) | `stage` (`uptrend`/`downtrend`/`topping`/`basing`/`sideways`), `risk`, description. |
| (signal rows) | Reversal signals generated from the most recent peak's matches only, each with a `signal_type` and `confidence`. |
| `summary` | `status`, `min_drop_threshold` (the *effective*, ATR-adjusted value actually used this run -- see F1/F2), `total_peaks`, `new_snapshots`, `total_patterns`, `n_matches`, `n_signals`, `current_stage`, `current_risk`, `dominant_signal`. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` (on the `summary` row) | Meaning |
|---|---|
| `completed` | Normal run, peaks/matches/signals/lifecycle all computed. |
| `no_data` | No bars supplied. |
| `no_peaks` | Bars supplied, but no peaks detected -- **this is the status a 1min/5min run without a real peak-drop threshold would frequently land in**, per F1. |

## 7. Comprehensive explanation  *(for humans only)*

**What this angle is grounded in.** Automatically detecting local price
extrema and asking whether the resulting patterns carry real predictive
information is a real, established line of research -- Lo, Mamaysky &
Wang's kernel-regression approach found, across three decades of U.S.
stock data, that several classical chart patterns do carry some real
incremental information, though the finding is explicitly modest ("may
have some practical value"), not a strong validation of technical
analysis broadly [TL1]. This angle's own peak/trough detection plus
KNN-matching-against-history approach is a reasonable, related design
built on that same general premise, even though it isn't a direct
implementation of the paper's specific kernel-regression method.

**The threshold gap, concretely (F1/F2).** At `1min` or `5min`, this
angle silently inherits the `1H` threshold (-3.0%) because those two
keys are simply absent from `_MIN_PEAK_DROP_PCT`. The ATR-based
adjustment sitting right next to it looks, at a glance, like it should
compensate -- but tracing the actual `min()` logic shows it can only
tighten the threshold, never loosen it, so it provides no relief for the
missing-entry case. In practice, this likely means 1min/5min runs of
this angle spend much of their time in the `no_peaks` status, with the
whole matching/lifecycle/signal machinery downstream of peak detection
never engaging at those timeframes -- not because there's nothing
happening on the chart, but because the bar to count as a "peak" is
calibrated for a much coarser timeframe than what's actually being fed
in.

**What's genuinely careful here.** Two things stand out on direct
reading, independent of F1/F2: the walk-forward `before_ts` filter
(every query peak is compared only against strictly earlier history,
never a same-or-later one), and the `outcome_mature` handling (a
snapshot's outcome is only trusted for matching once its forward
window has actually completed, with legacy rows treated conservatively
as immature so they get recomputed with a real finalized outcome). Both
are the same class of look-ahead-safety discipline already found and
credited in `kalman_filters` and `regime_analysis`.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| TL1 | Lo, Mamaysky & Wang, "Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation," NBER Working Paper 7613, March 2000 (abstract page) | Systematic, kernel-regression-based approach to detecting local extrema for technical pattern recognition; the paper's own hedged conclusion that several technical indicators provide incremental information and "may have some practical value" over a 31-year U.S. stock sample. | https://www.nber.org/system/files/working_papers/w7613/w7613.pdf |
| -- | Direct read of `vinu_initial_analysis/angles/trend_lifecycle/compute.py`'s `_MIN_PEAK_DROP_PCT` dict and the `atr_adj`/`effective_min_drop` computation | Confirmed the missing `1min`/`5min` dictionary entries and traced the `min()` logic to show the ATR adjustment cannot compensate for them. | (local code read, 2026-09-24) |
