# 09 — kalman_filters

- **Angle id:** `kalman_filters`
- **Cluster:** A — Classical statistical forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/kalman_filters/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`) --
  implemented via statsmodels' `UnobservedComponents(level="local linear
  trend")`, a two-state (level, trend) structural time series model that
  **is** a Kalman filter/smoother under the hood.
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Recursively estimates a hidden "true" price level and its local trend
from noisy close prices, correcting the estimate one observation at a
time. **This is a state estimate of the present, not a forecast** -- the
spec explicitly calls that out. A separate `filtered_trend` sign is used
as a directional signal in the backtest, not a price prediction.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | The observed close price is a noisy measurement of a hidden **level + local trend** state, updated recursively via predict-then-correct. | code's own docstring, structure cross-checked against [K2] |
| A2 | **Filtered** state (using only past and present observations) and **smoothed** state (using the whole series, forward and backward) are different quantities -- smoothed state at any interior point uses information from *after* that point, which would be look-ahead bias if fed into a causal prediction. | [K2] |
| A3 | At the **final time step of the series**, filtered and smoothed estimates use the exact same information (there is no "later" data), so the recursion formally starts there with **filtering and smoothing distributions equal**. | [K2] |
| A4 | Noise variances (how much to trust new observations vs. the existing state estimate) are fit by maximum likelihood, not chosen by hand. | code's own docstring |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Fixed-interval smoothing (estimate the whole path `[0, T]` given all `T` observations) | The backward recursion is only needed because, at interior points, the filtering and smoothing distributions genuinely differ; **at the last time step they provably coincide by construction**, since there's no future data left to condition on beyond it. | [K2] |
| R2 | Direct test in the real production container, local-linear-trend model fit on a synthetic trending+noisy series (150 points) | `filtered_level == smoothed_level`, `filtered_trend == smoothed_trend`, and even `filtered_state_cov == smoothed_state_cov` at the last index -- **exactly equal**, not just close. | (local test, see below) |
| R3 | Kalman filter, general predict-update cycle | Two-step recursion: **predict** the next state from the dynamic model, then **update/correct** it using the new noisy measurement, weighted by relative uncertainty (the Kalman gain). | general framing, cross-checked against [K2]'s problem formulation |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `compute()`'s live output includes **both** `filtered_level`/`filtered_trend` **and** `smoothed_level`/`smoothed_trend`, computed from the exact same fit on the exact same data. | R1/R2: filtered and smoothed states are mathematically identical at the series' final point. | **Confirmed: the two fields are always numerically identical in the live path.** Verified directly (R2), not just from theory. This is genuinely different from the *backtest*, which correctly keeps smoothed state completely separate (see F2) -- but in the single-shot live `compute()` call, "smoothed" carries no new information over "filtered." A reader could easily assume `smoothed_*` reflects some richer, whole-history-informed estimate the way it's described everywhere else in this codebase (`run_smoothed_diagnostic`'s own docstring calls it a "hindsight 'ground truth'") -- but at the point it's actually reported, hindsight and causal estimates are the same number. |
| F2 | `backtest.py` never uses `smoothed_state` inside the walk-forward loop -- only `run_smoothed_diagnostic()`, a separate whole-history-only function, touches it, and its own docstring explains exactly why (look-ahead bias at *interior* points). | Exactly matches the textbook distinction: smoothing at interior points uses future information; filtering never does [K2]. | **Correct and well-documented.** This is the one angle researched so far where the code's own comments show real, specific awareness of a subtle correctness trap (look-ahead bias) and design around it deliberately -- worth noting as a positive example, not just a source of findings. |
| F3 | Directional backtest signal is `filtered_trend`'s sign, not a price forecast; the naive baseline is **persistence** (repeat the last realized direction), not "predict flat." | Code's own docstring explains a flat-prediction naive baseline would be degenerate for direction (markets essentially never close exactly flat), citing an illustrative ~51.2% hit rate for the persistence baseline instead. | **Sound reasoning**, consistent with the same degenerate-flat-baseline problem already flagged for `dlinear`. This angle avoids it by using the correct comparison baseline for a *directional* task rather than reusing the *point-forecast* naive pattern. |
| F4 | Reports `filtered_level_std`/`filtered_trend_std` (state uncertainty), derived from `filtered_state_cov`. | State covariance is a core, standard part of the Kalman recursion's output, not an add-on. | Correct and useful -- lets a reader see how confident the estimate is, not just its value. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `filtered_level` | Causal (online) estimate of the hidden price level at the most recent bar -- uses only data up to and including that bar. |
| `filtered_level_std` | Standard deviation of that level estimate's uncertainty. |
| `filtered_trend` | Causal estimate of the local trend (slope) at the most recent bar. Its **sign** is the directional signal used in the backtest. |
| `filtered_trend_std` | Standard deviation of the trend estimate's uncertainty. |
| `smoothed_level` / `smoothed_trend` | The two-pass (whole-history) terminal state estimate. **In the live `compute()` path these are always identical to `filtered_level`/`filtered_trend`** -- see F1. Only meaningfully different from filtered values at points *before* the series' end, which this angle never reports. |
| `last_observed_close` | The actual last close price (not a state estimate). |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Fit succeeded. | All fields above. |
| `no_data` | No price bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (100 by default) closes. | + `n_observations`. |
| `fit_failed` | statsmodels raised during `.fit()`. | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What a Kalman filter is.** A recursive predict-then-correct
estimator: given a model of how a hidden state evolves and a model of
how noisy measurements relate to that state, it predicts the next
state, then corrects that prediction using the new measurement, weighted
by how much each source is trusted (the Kalman gain) -- the standard predict/update framing, consistent with [K2]'s problem formulation. Filtering
uses only past and present measurements. Smoothing goes further: it also
runs a second, *backward* pass using future measurements too, producing
a better (lower-variance) estimate of the state at any interior time
point -- at the cost of needing the whole series up front, which makes
it inherently non-causal [K2].

**Why `compute.py`'s smoothed fields don't add information here (F1).**
The reason smoothing helps at interior points is that it borrows
information from observations that come *after* that point. At the very
last point of the series, there *is* no "after" -- the backward pass has
nothing left to correct with, so by construction the smoothing
distribution at the final time step is identical to the filtering
distribution there [K2]. This isn't a subtle numerical coincidence: it
was verified directly by fitting the same model class our code uses
(`UnobservedComponents`, local linear trend) inside the real production
container and comparing `filtered_state[:, -1]` to `smoothed_state[:,
-1]` -- level, trend, and even their covariances came back exactly
equal. Since `compute()` only ever reports the *last* index of the
series, its `smoothed_*` fields carry zero extra information beyond
`filtered_*` -- they're the same numbers under a different name.

**Why this doesn't touch the backtest's correctness.** This is purely
about the live single-shot output. `backtest.py` never uses smoothed
state inside its walk-forward loop at all -- its own docstring is
explicit that doing so would leak future information into a causal
step. `run_smoothed_diagnostic()` is the one place smoothed state is
used, and there it's computed once over the *entire* history and never
tagged into a per-step row, so it genuinely does differ from the
filtered path at the interior points it's estimating -- that function's
"hindsight ground truth" framing is accurate for what it actually
computes. The redundancy (F1) is specific to `compute.py`'s live output,
where "smoothed" is computed but, because it's evaluated only at the
series' terminal point, degenerates to "filtered again."

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| K2 | Simo Särkkä, "Lecture 7: Bayesian Smoother, Gaussian and Particle Smoothers" (Aalto University course notes, 2016) -- slides "Problem Formulation" and "Types of Smoothing Problems" | Fixed-interval smoothing definition; predict/filter/smooth as three distinct estimation problems; the backward recursion exists because filtering and smoothing distributions differ at interior points; explicit statement: "on the last step, the filtering and smoothing distributions coincide: p(x_T \| y_1:T)." | https://users.aalto.fi/~ssarkka/course_k2016/handout7.pdf |
| -- | Direct test in the production container `vinu-components-initial-analysis-api-1`, statsmodels' `UnobservedComponents(level="local linear trend")` fit on a synthetic 150-point trending+noisy series | `filtered_state[:, -1]` and `smoothed_state[:, -1]` (level, trend, and their covariances) are exactly equal at the last index. | (local test, 2026-09-24) |

**Tried and not used:**
- Kalman (1960), "A New Approach to Linear Filtering and Prediction
  Problems" -- not fetched; [K2] and the direct container test were
  sufficient to verify the specific claim needed (filtered = smoothed at
  the terminal point), and citing the original 1960 paper without
  actually reading it would violate this folder's own citation rule.
