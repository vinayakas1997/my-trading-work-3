# 06 — exponential_smoothing

- **Angle id:** `exponential_smoothing`
- **Cluster:** A — Classical statistical forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/exponential_smoothing/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Holt's linear trend method (double exponential smoothing): fits a level
and a trend to recent closing prices, weighting recent bars more than
old ones, and forecasts one step ahead as level + trend. No seasonal
component. A cheap, classical baseline, not a sophisticated signal.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | The series can be decomposed into a **level** and a **trend**, each updated by an exponentially-weighted average of past values. | [E1] |
| A2 | The trend, once estimated, **continues at the same rate indefinitely** into the forecast (no damping). | [E1] |
| A3 | No seasonal component -- appropriate for series with "no reliable fixed seasonal period." | code's own design rationale |
| A4 | Initial level/trend values are chosen by **minimizing one-step-ahead squared error** over the whole fitted history, same as the smoothing parameters themselves. | [E1], [E2] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Undamped linear trend, multi-step forecasts | "Display a constant trend... indefinitely," and empirically these methods "tend to over-forecast, especially for longer forecast horizons." | [E1] |
| R2 | Damped trend (φ between 0 and 1) | Fixes the over-forecasting: the trend "approach[es] a constant some time in the future" instead of continuing forever. | [E1] |
| R3 | Simple exponential smoothing fit to a true random walk | The optimal smoothing weight drifts toward the edge of its range (example given: "0.9999") -- the fit degenerates into using only the most recent observation, i.e. the naive forecast. | [E3] |
| R4 | Holt's method vs. ARIMA | Holt's linear trend method **is** an ARIMA(0,2,2) model -- not a separate family, a specific case of it. | [E3] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | `ExponentialSmoothing(close, trend="add", seasonal=None, initialization_method="estimated")` -- **no damping** (statsmodels default `damped_trend=False`). | Undamped trend "continue[s]... indefinitely" and over-forecasts at longer horizons [E1]; damping is the documented fix [E1]. | **Low practical risk here specifically**, because this angle only ever forecasts **1 step ahead** -- the over-forecasting problem [E1] describes grows with horizon, and at h=1 the forecast is just `level + trend`, not yet compounding. The risk moves downstream: the fitted `trend` field itself is reported and could be read by a caller as "the ongoing direction," which is exactly the indefinite-continuation assumption [E1] warns is unreliable beyond the very near term. |
| F2 | `seasonal=None`. | Matches the code's own stated rationale (no fixed seasonal period in daily equity data) -- not contradicted by any source read. | Reasonable, undisputed. |
| F3 | Output field `beta` = `smoothing_trend`, the **trend's own smoothing weight**, not the trend value itself (that's the separate `trend` field). | Parameter naming confirmed against statsmodels docs [E2]. | Not a bug, but a real naming trap: a reader skimming field names could easily conflate `beta` (a 0-1 weight) with `trend` (a price-per-bar slope) the same way `alpha` (level's weight) could be misread as the level itself. |
| F4 | `trend` field is written as `None` if `res.trend is None`. | Since `trend="add"` is always passed, statsmodels should always populate a trend series in the fit result. | Effectively unreachable in the current code path -- a defensive branch guarding against a statsmodels internal case that shouldn't occur here, not a live risk. |
| F5 | Ships with `naive_baseline.py` (RMSE/MAE against last-close-repeated), unlike `dlinear`. | R3 above implies that on data close to a random walk, Holt's own fit could converge toward behaving like the naive forecast anyway. | **Good design** -- this is exactly the comparison [04-dlinear-angle.md](04-dlinear-angle.md) flagged as missing. Whether the fitted `alpha`/`beta` on real tickers actually do drift toward the random-walk extreme (R3) was **not tested here** -- it would need fitting on real bars and reading back the parameters, which is a natural next check, not something this research pass computed. |
| F6 | `MIN_OBSERVATIONS` raised from the code's original floor of 10 to 100 (config default), per the module's own comment, "same consistency move as ARIMA's 30->100, DLinear's 80->100." | -- (internal consistency decision, not a literature question) | Consistent with the same tightening already noted for `arima` and `dlinear`; no new finding. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `forecast` | One-step-ahead point forecast: `level + trend`. |
| `alpha` | The **level's** smoothing weight (`smoothing_level`), 0-1. Higher = level tracks recent prices more closely. |
| `beta` | The **trend's** smoothing weight (`smoothing_trend`), 0-1. **Not the trend value itself** -- see F3. |
| `level` | The fitted level at the last observed bar. |
| `trend` | The fitted trend (slope per bar) at the last observed bar. Can be `null` -- see F4 (not expected to occur in practice). |
| `sse` | Sum of squared one-step-ahead fitting errors over the whole history -- a fit-quality number, not a forecast-accuracy number (same caveat as `dlinear`'s `train_loss`). |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Fit succeeded, forecast produced. | All fields above. |
| `no_data` | No price bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_OBSERVATIONS` (100 by default) closes. | + `n_observations`. |
| `fit_failed` | statsmodels raised during `.fit()` or `.forecast()`. | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What Holt's method is.** Simple exponential smoothing tracks only a
level (a weighted average of the past). Holt's extension adds a second
weighted average that tracks how fast the level is changing -- the
trend -- and the forecast is level plus trend times the number of steps
ahead [E1]. Both weights (`alpha` for the level, `beta*` for the trend,
called `smoothing_trend` in statsmodels) are fit by minimizing one-step
squared error over the whole history, along with the starting level and
trend values themselves [E1][E2].

**Where it sits relative to ARIMA and the random walk.** Holt's linear
trend method isn't a separate technique from ARIMA -- it's the specific
case ARIMA(0,2,2) [E3]. And simple exponential smoothing has a known
degenerate case: fit it to a pure random walk, and the optimal smoothing
weight pushes toward 1, which just means "predict tomorrow equals
today" -- the naive forecast [E3]. `01-arima-angle.md`'s own research
found daily-equity prices are close to a random walk. If that holds for
whatever ticker/timeframe this angle runs on, this angle's own `alpha`
could plausibly land close to that same extreme -- worth checking
against real fitted values on real tickers, not asserted here as a
fact, since it wasn't tested in this pass.

**Why the no-damping choice matters less than it might.** The published
warning about undamped trend is specifically about **longer-horizon**
forecasts drifting further and further from reality [E1]. This angle
only ever asks for one step ahead, where the effect is smallest. The
place the warning still applies is if a downstream reader treats the
`trend` field itself as "the expected ongoing direction" rather than
"the slope of the last few bars" -- that's exactly the assumption the
literature says breaks down.

**Why `beta` isn't the trend (F3).** In Holt's own notation the trend
value is often written `b_t`; the *smoothing weight* that updates it is
a different Greek letter (`β*`) [E1]. Our field names keep that
distinction (`trend` vs `beta`), which is correct, but the two are easy
to conflate at a glance since both are "trend-related."

**The naive comparison this angle already has.** Unlike `dlinear`
(flagged in [04-dlinear-angle.md](04-dlinear-angle.md) as missing this
entirely), `exponential_smoothing` ships `naive_baseline.py`, comparing
RMSE/MAE against a flat "repeat last close" forecast, with no
direction-hit metric since a naive forecast is always "flat" by
construction -- the code's own stated reasoning, and a correct one.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| E1 | Hyndman & Athanasopoulos, *Forecasting: Principles and Practice*, 3rd ed., "8.2 Holt's linear trend method" (full page, incl. equations) | Level/trend/forecast equations; α/β* definitions; initial values fit by minimizing SSE; undamped trend continues indefinitely and over-forecasts at longer horizons; damped trend as the fix. | https://otexts.com/fpp3/holt.html |
| E2 | statsmodels documentation, `statsmodels.tsa.holtwinters.ExponentialSmoothing` | `trend='add'` vs `'mul'`; `seasonal=None`; `damped_trend` default `False`; `initialization_method='estimated'` (optimized during fit) vs `'heuristic'`/`'legacy-heuristic'`/`'known'`. | https://www.statsmodels.org/stable/generated/statsmodels.tsa.holtwinters.ExponentialSmoothing.html |
| E3 | Robert Nau (Duke Fuqua School of Business), "Statistical forecasting: notes on regression and time series analysis" | "Holt's linear smoothing model is an ARIMA(0,2,2) model"; simple exponential smoothing fit to a near-random-walk series drives optimal alpha toward 1 (example: 0.9999); caution against extrapolating fitted trends far into the future given widening uncertainty. | https://people.duke.edu/~rnau/411fcst.htm |

**Tried and not used:**
- Suryoday et al., "Forecasting Stock Market Price of Gold, Silver,
  Crude Oil and Platinum by Using Double Exponential Smoothing, Holt's
  Linear Trend and Random Walk," ADS abstract page -- the page returned
  an HTTP 405 error and could not be read, so its reported comparison
  is not cited here.
