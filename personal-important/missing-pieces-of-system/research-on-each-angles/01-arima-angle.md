# 01 — arima

- **Angle id:** `arima`
- **Cluster:** A — Classical statistical forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/arima/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

ARIMA predicts the next price from the recent price history using a
simple linear formula. It first turns the price series into price
*changes* (so the pattern is steady over time), then learns how much
each recent change and recent error tends to carry into the next one. It
gives one next-bar price forecast plus a 95% range. It is a transparent
baseline, not a sophisticated model.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | After differencing, the series is **stationary** -- its statistical properties don't depend on when you look at it. | [C1] |
| A2 | The relationship between past and next values is **linear**. | [C5] |
| A3 | The errors (residuals) are **uncorrelated and normally distributed** -- the 95% range is only correct if this holds. | [C3] |
| A4 | The errors have **constant variance**. Often not true for financial data; pairing ARIMA with GARCH is the standard way to relax this. | [C5] |
| A5 | AIC is a valid way to choose **p and q**, but **not d** (the amount of differencing). | [C4] |

## 3. Assumption results  *(passed to the LLM)*

What published sources report when these assumptions/parameters are set
a particular way:

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | d=1 on a daily stock price | Google's daily closing price was non-stationary, but its daily changes were stationary -- so one difference (d=1) is the standard setting for price levels. | [C1] |
| R2 | d=1 with no constant | ARIMA(0,1,0) with no constant **is** a random walk; with c=0 and d=1 the long-term forecast settles to a flat constant (no drift). | [C2] |
| R3 | Compared to the naive "no change" forecast | The naive forecast "works remarkably well for many economic and financial time series"; a method that can't beat it "is not worth considering." | [C6] |
| R4 | Using the 95% interval | ARIMA prediction intervals "tend to be too narrow," because they ignore uncertainty in the fitted parameters and in the chosen order. | [C3] |
| R5 | Fixed ARIMA(5,1,0), monthly index data 1985-2018, walk-forward refit each step | An LSTM had 84-87% lower average error than ARIMA. **Caveat:** monthly data and a fixed, unoptimized order; no naive baseline was included. Does not transfer directly to our intraday-to-daily, AIC-selected setup. | [C5] |

## 4. How our code compares to the literature

Useful, not embarrassing -- these are the real gaps this research found.

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Picks d (0 or 1) by comparing AIC across models with different d (`_ORDER_GRID` in `compute.py`). | AIC values between models with different d are "not comparable" [C4]. d should be chosen first (e.g. KPSS unit-root test [C1]), AIC only for p and q. | **Conflicts with the textbook.** Whether statsmodels' state-space likelihood changes this was **not verified** -- its docs page didn't cover it. Worth a follow-up. |
| F2 | Uses statsmodels' default trend. | statsmodels: constant by default when d=0, **no constant when d>0** [C7]. With d=1, that means no drift [C2]. | A d=1 forecast will never carry a trend forward. Readers should not read "flat forecast" as "no trend exists." |
| F3 | Reports a 95% interval (`confidence_interval`). | Intervals assume uncorrelated, normal errors [C3] and constant variance [C5]; financial data often breaks this, and intervals tend to be too narrow anyway [C3]. | Treat the interval as optimistic. `backtest.py`'s CI-coverage hit rate measures exactly how optimistic, per ticker. |
| F4 | Has `naive_baseline.py`, run through the same walk-forward harness. | Every method must be compared to the naive forecast [C6]. | **Already follows the textbook.** |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `forecast` | The one-step-ahead predicted close price. **Note:** the current glossary (`angle_glossary.py`) calls this `forecast_price` -- that field does not exist. |
| `confidence_interval` | `[lower, upper]` bounds of the forecast. |
| `confidence_level` | Always `0.95`. |
| `order` | `{"p", "d", "q"}` -- the order the AIC grid picked. `d=1` means it modeled price changes, `d=0` means raw prices. |
| `aic` | The winning model's AIC. Only comparable to other ARIMA fits on the same data. |
| `n_observations` | How many closing prices the model was fit on. |
| `symbol`, `analysis_at`, `angle` | Identification: ticker, UTC timestamp of the run, `"arima"`. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Fit succeeded, forecast produced. | All fields above. |
| `no_data` | No price bars were supplied at all. | Identification fields only. |
| `insufficient_data` | Fewer than 100 closing prices (default, overridable via `VINU_ARIMA_MIN_OBSERVATIONS`). | + `n_observations`. |
| `fit_failed` | No order in the grid produced a valid (finite-AIC) fit. | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What ARIMA(p, d, q) is.** AutoRegressive Integrated Moving Average.
"Integrated" is the reverse of differencing [C2]. The three numbers:
- **d** -- how many times the series is differenced (each value replaced
  by its change from the previous one). Prices usually trend, so their
  average level drifts over time; differencing once turns prices into
  price changes, which usually have a stable average [C1].
- **p** -- how many past values (of the differenced series) feed the
  forecast. "Autoregressive": the series regressed on its own past.
- **q** -- how many past forecast errors feed the forecast. "Moving
  average" of past errors, not a moving average of prices.

**Special cases worth knowing** [C2]: ARIMA(0,0,0) with no constant is
pure white noise; ARIMA(0,1,0) with no constant is a random walk (the
forecast is just the last price); with a constant it's a random walk
with drift.

**What our implementation does, step by step** (`compute.py`):
1. Takes the close prices for the requested timeframe; needs at least 100.
2. Fits 16 candidate models: d ∈ {0, 1}, p ∈ {0, 1, 2}, q ∈ {0, 1, 2},
   excluding p=0, q=0. The code doesn't state why; note that for d=1
   that excluded pair is exactly the random walk [C2], which
   `naive_baseline.py` already covers separately.
3. Keeps the one with the lowest AIC (see F1 for why this is shaky across
   different d).
4. Forecasts exactly one bar ahead, with a 95% interval.

**How it's backtested** (`backtest.py`, `naive_baseline.py`): walk-
forward -- at each step the model only sees history up to that point,
forecasts the next bar, then the real next bar is revealed. Scored two
ways: (a) whether the real close landed inside ARIMA's own 95% interval
(CI coverage -- a well-calibrated 95% interval should contain the truth
about 95% of the time; lower means it's too narrow, see R4/F3), and (b)
point error compared against the naive "no change" forecast run through
the same harness (R3/F4). On the two finest timeframes (1min, 5min), the
full 16-model grid isn't re-run every step -- measured at ~0.53s per grid
fit vs ~0.003s to extend an existing fit, about 170x cheaper -- so the
previous fit is extended between scheduled refits.

**Why it's in the system at all.** As Cluster A's transparent baseline:
if a far more complex model (Cluster B) can't beat ARIMA, and ARIMA
can't beat "no change," that is real information, not a failure of the
angle.

**Where it's weakest.** Volatility clustering in real markets breaks the
constant-variance assumption (A4) -- which is exactly what Cluster C's
`garch` angle measures. Reading ARIMA's interval next to GARCH's
volatility forecast is the natural pairing the literature itself
suggests [C5].

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| C1 | Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* (3rd ed.), page "Stationarity and differencing" | Definition of stationarity; Google stock price non-stationary, daily changes stationary; KPSS test for choosing d. | https://otexts.com/fpp3/stationarity.html |
| C2 | Same book, page "Non-seasonal ARIMA models" | Meaning of p, d, q; special cases (random walk = ARIMA(0,1,0)); long-term forecast behavior by c and d. | https://otexts.com/fpp3/non-seasonal-arima.html |
| C3 | Same book, page on ARIMA forecasting | Prediction intervals assume uncorrelated, normally distributed residuals; "tend to be too narrow." | https://otexts.com/fpp3/arima-forecasting.html |
| C4 | Same book, page on ARIMA estimation and order selection | AIC/AICc good for p and q, "not good guides" for d; AIC across different d "not comparable." | https://otexts.com/fpp3/arima-estimation.html |
| C5 | Siami-Namini & Siami Namin (2018), "Forecasting Economics and Financial Time Series: ARIMA vs. LSTM," arXiv:1803.06386 | Constant-variance assumption and GARCH (p.4); ARIMA as linear regression-based (p.10); data = monthly indices 1985-2018, fixed ARIMA(5,1,0), rolling refit, 84-87% error reduction (abstract, pp.9-11). Note: its Table 1 column headers appear swapped ("Test 70% / Train 30%") vs. the text's 70% train. | https://arxiv.org/abs/1803.06386 |
| C6 | Same book as C1, page on simple forecasting methods | Naive forecast "works remarkably well" for financial series; = random-walk forecast; new methods must beat it. | https://otexts.com/fpp3/simple-methods.html |
| C7 | statsmodels documentation, `statsmodels.tsa.arima.model.ARIMA` | Default trend: constant when no integration, none when integrated. | https://www.statsmodels.org/stable/generated/statsmodels.tsa.arima.model.ARIMA.html |

**Tried and not used** (so nobody re-cites them by mistake):
- Chen (2026), arXiv:2608.26106 -- surfaced by a search for ARIMA-vs-
  random-walk studies, but on reading it **does not test ARIMA at all**
  (XGBoost/RF/LightGBM/logistic regression only).
- Ariyo, Adewumi & Ayo (2014), "Stock price prediction using the ARIMA
  model," UKSim -- widely cited, but the full text couldn't be opened
  (ResearchGate 403, Semantic Scholar rendered empty). Not cited, since
  its claims couldn't be checked.
