# 20 — regime_analysis

- **Angle id:** `regime_analysis`
- **Cluster:** C — Volatility & drawdown risk
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/regime_analysis/`
  (`compute.py`, `backtest.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Classifies each bar into one of four regimes -- `bull`, `bear`,
`high_vol`, `sideways` -- using fixed rules (20-bar return and a
120-bar-baseline volatility z-score), reports the current regime, a
per-regime Sharpe-style stats table, and a transition matrix. **All the
window sizes and thresholds are counted in bars, not real time**, and
this angle is declared across 8 very different timeframes (1min through
1M) -- see F1 for why that means "bull"/"bear" mean very different
real-world things depending on which timeframe a given call uses.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | A cumulative 20-bar return above +1% / below -1% is a meaningful bull/bear signal, and a volatility z-score (against a 120-bar trailing baseline) above 1.0 overrides both to signal `high_vol`. | code's own fixed thresholds |
| A2 | *(Code's own prior fix, cited in its docstring)* Computing the volatility threshold as a quantile over the **entire** sample series is a look-ahead leak -- an early bar's regime could depend on volatility that hadn't happened yet. A rolling (point-in-time) baseline avoids this. | code's own docstring, citing a defect found and fixed elsewhere in this codebase (`news_price_causality/regime_features.py`) |
| A3 | *(Literature's alternative approach)* A market's regime can instead be treated as a genuinely **unobservable (latent) state** that follows a first-order Markov chain, inferred probabilistically from the data itself (via maximum likelihood) rather than assigned by fixed hand-set thresholds. | [RG1] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Hamilton's (1989) Markov-switching model | "The switching mechanism is controlled by an unobservable state variable that follows a first-order Markov chain... a structure may prevail for a random period of time, and it will be replaced by another structure when a switching takes place" -- regime membership and the probability of switching are both *estimated from the data*, not fixed in advance. | [RG1] |
| R2 | Why nonlinear regime-aware models exist at all | Linear models "are unable to represent... asymmetry, amplitude dependence and volatility clustering" -- e.g. growth rates "fluctuate around a higher level and are more persistent during expansions, but... stay at a relatively lower level and less persistent during contractions." | [RG1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `RETURN_WINDOW=20`, `VOL_WINDOW=21`, `VOL_BASELINE_WINDOW=120`, `BULL_BEAR_THRESHOLD=0.01` are all counted in **bars**, applied unchanged across all 8 declared `time_formats` (1min, 5min, 15min, 1H, 4H, 1D, 1W, 1M). | -- (internal, verifiable from the code alone) | **Real, confirmed inconsistency.** 20 bars means 20 minutes at `1min`, roughly a month at `1D`, and roughly 1.7 years at `1M`. Requiring the *same* fixed +1%/-1% cumulative move to call something "bull"/"bear" regardless of which of those windows is in play means the labels mean structurally different things per timeframe: at `1min`, a 1% move in 20 minutes is a sharp, unusual intraday swing; at `1M`, a stock failing to clear +1% over 20 months would be unusual on the downside. Same root-cause pattern already found in `peer_relative_strength` (F1/F3 there): fixed, bar-counted constants applied identically across a wide `time_formats` declaration that spans very different real durations. |
| F2 | `classify_regime` checks `vol_z > 1.0` (high_vol) **before** checking the return-based bull/bear rule -- a bar with a strong positive 20-bar return but elevated volatility gets classified `high_vol`, not `bull`. | -- | Not necessarily wrong, but the priority ordering isn't explained anywhere in the code or docs -- a caller reading `regime: "high_vol"` can't tell from the row alone whether the underlying trend was actually up, down, or flat; that information is discarded once `high_vol` wins the priority check. |
| F3 | Regime classification is a deterministic, fixed-threshold rule applied bar-by-bar. | The standard statistical treatment of "market regime" (Hamilton 1989) treats the regime as a **latent variable**, estimated jointly with the model's other parameters via maximum likelihood, with regime persistence and switching probabilities themselves *learned from the data* rather than fixed [RG1]. | **A real, disclosed design simplification, not a bug.** Fixed thresholds are simpler, deterministic, and cheap to compute per-bar -- reasonable engineering trade-offs -- but they don't adapt to a given ticker's own typical volatility/return distribution the way a fitted Markov-switching model would, and a bar sitting just above vs. just below a hard threshold (e.g. `ret_20d = 0.0099` vs `0.0101`) can flip its label with no real change in underlying conditions. |
| F4 | Per-regime `sharpe = grp["ret"].mean() / grp["ret"].std() * af`, no risk-free rate subtracted. | Already researched and cited in [02-backtesting_44_metrics-angle.md](02-backtesting_44_metrics-angle.md) (F1 there): a proper Sharpe ratio measures excess return over a riskless benchmark, not raw return over volatility. | **Same known limitation, not re-derived here** -- this angle's `sharpe` field inherits the identical "return/volatility ratio, not textbook Sharpe" gap already documented for `backtesting_44_metrics`. |
| F5 | `current_regime` (the most recent bar's regime) is reported as its own separate row, explicitly distinguished in a code comment from `regime_stats`' highest-`pct_of_time` regime -- the comment notes this exact confusion was "a confirmed bug at the vinu-strategy call site that consumed this angle." | -- | **A previously-caught real bug, already fixed and guarded against with a clarifying comment** -- a positive example, like the look-ahead-leak fix in A2. |
| F6 | `transition_prob` is always paired with its own `n_from_regime` denominator in the same row. | -- | Sound, consistent with this codebase's stated "never present a rate without its sample size" discipline (seen elsewhere, e.g. `pnl_attribution`'s CI fields). |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

Rows are distinguished by `metric`:

**`metric: "current_regime"`** -- one row, the most recent bar's classification:

| Field | Meaning |
|---|---|
| `regime` | `bull`/`bear`/`high_vol`/`sideways` as of the latest bar. |
| `bar_ts` | Timestamp of that bar. |
| `ret_20d`, `vol_trailing_z` | The two classification inputs at that point. |

**`metric: "regime_stats"`** -- one row per regime seen in the analyzed history:

| Field | Meaning |
|---|---|
| `count`, `pct_of_time` | How many bars fell in this regime, and what fraction of the whole analyzed history that is. |
| `total_return`, `avg_return`, `std_return` | Compounded and per-bar return stats **while in this regime** (not necessarily contiguous periods). |
| `sharpe` | `avg_return / std_return`, annualized -- **not textbook Sharpe**, see F4. |
| `win_rate` | Share of bars in this regime with a positive return. |

**`metric: "regime_transitions"`** -- one row: total count of regime changes across the whole series.

**`metric: "transition"`** -- one row per observed `(from, to)` regime pair: `count`, `n_from_regime`, `transition_prob`.

**Always present:** `symbol`, `analysis_at`, `angle`.

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| *(absent)* | Success -- rows returned directly, no `status` field (same "success = no status key" pattern already seen in `backtesting_44_metrics`/`peer_relative_strength`). | Metric rows above. |
| `no_data` | No bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (`VOL_BASELINE_WINDOW + VOL_WINDOW` = 141 by default) bars, or the point-in-time frame ended up empty after dropping rows with incomplete rolling windows. | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**The look-ahead fix this module already made.** The docstring is
explicit about a real prior defect: computing the volatility threshold
as a quantile (`vol.quantile(0.7)`) over the *entire* sample meant an
early bar's regime label implicitly depended on volatility that hadn't
happened yet at that point in history -- a classic look-ahead leak. The
fix (a rolling 120-bar baseline mean/std, so every bar's z-score depends
only on bars up to and including itself) is correct and was adopted
specifically because a sibling module (`news_price_causality`) had
already found and fixed the identical issue, avoiding two diverging
regime definitions in the same codebase.

**Why fixed-bar thresholds across 8 timeframes is the live gap (F1).**
None of `RETURN_WINDOW`, `VOL_WINDOW`, `VOL_BASELINE_WINDOW`, or
`BULL_BEAR_THRESHOLD` change with `time_format` -- they're plain integer
bar counts and a flat percentage. Since this angle is declared across
timeframes spanning three orders of magnitude in real duration (minutes
to years), the *meaning* of "bull" silently shifts underneath the same
label depending on which timeframe a caller happens to request. This
mirrors the same category of issue already found in
`peer_relative_strength`, just manifesting as threshold miscalibration
rather than a data-alignment failure.

**The rule-based vs. latent-state framing (F3).** This isn't presented
as "the code is wrong" -- fixed-threshold regime rules are common,
cheap, and easy to reason about. But it's worth being precise about what
kind of method this is: Hamilton's regime-switching model, the standard
academic reference point for "market regime," treats the regime itself
as something the data reveals through estimation, with the model
learning both how persistent each regime is and how likely a switch is
[RG1]. This angle instead hand-sets both the boundaries (fixed
thresholds) and, implicitly, the "persistence" (however long consecutive
bars happen to sit on the same side of those thresholds) -- a much
simpler, deterministic alternative to the same underlying question.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| RG1 | Chung-Ming Kuan, "Lecture on the Markov Switching Model" (Academia Sinica lecture notes, citing Hamilton 1989), pp. 1 | Markov-switching model definition: regime as an unobservable state following a first-order Markov chain, persisting for a random duration before switching; motivation for nonlinear regime-aware models over linear ones (asymmetry, amplitude dependence, volatility clustering not captured by a single linear model). | https://homepage.ntu.edu.tw/~ckuan/pdf/Lec-Markov_note.pdf |
