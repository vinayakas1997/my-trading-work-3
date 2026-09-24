# 04 — dlinear

- **Angle id:** `dlinear`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/dlinear/`
  (`compute.py`, `backtest.py`, `spec.yaml`) -- note: **no `naive_baseline.py`**
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

DLinear is a very small model trained from scratch on this ticker every
time it runs. It splits the last 30 closing prices into a smooth trend
(a moving average) and the wiggles around it, applies one simple
weighted sum to each, and adds them up to predict the next bar's price.
It then labels that prediction `up`, `down` or `flat`.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | The next value is a **linear** (weighted-sum) function of recent values. | [D1] |
| A2 | Splitting the series into **trend + remainder** with a moving average helps "when there is a clear trend in the data." | [D1] |
| A3 | The trend line at the edges is computed by **repeating the first/last value** as padding. | [D2] |
| A4 | A **longer look-back window** gives the linear model more to learn from. | [D1] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | DLinear vs. naive "repeat the last value," **Exchange-Rate** dataset (daily, 8 currencies), horizons 96/192/336/720 | MSE **tied** the naive baseline at 96 (0.081 vs 0.081) and 336 (0.305 vs 0.305); better at 192 (0.157 vs 0.167) and 720 (0.643 vs 0.823). On financial data, it roughly matches "do nothing" at half the horizons. | [D1] Table 2 |
| R2 | Naive "repeat last value" vs. Transformer models, same Exchange-Rate data | The naive baseline "surprisingly outperforms all Transformer-based methods on Exchange-Rate (around 45%)." | [D1] |
| R3 | Linear models with longer look-back windows | "Significantly boosted with the increase of look-back window size" (tested windows 24 to 720). | [D1] |
| R4 | Linear models vs. Transformers, 9 long-horizon benchmarks | Linear models beat the best Transformer "in most cases by 20% ~ 50%." | [D1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Trend = `nn.AvgPool1d(padding=2)`, which pads the edges with **zeros**. | Reference implementation repeats the first/last values instead [D2]. | **Confirmed deviation**, tested in the real production container: on a flat series of 1.0s, our trend reads **0.6 and 0.8 at the two newest bars** instead of 1.0. The trend is dragged toward the series average exactly where it matters most, and the "wiggle" part picks up a false bump. Training uses the same distortion, so the model may partly learn around it -- but it's not the published method, and its accuracy effect is unmeasured. Easy fix: pad by repetition, as [D2] does. |
| F2 | Moving-average window of **5**. | Reference default is **25** [D2]. | Our trend is much less smooth -- closer to the raw price. Possibly deliberate for a 30-bar window; not documented. |
| F3 | Look-back of **30** bars, predicting **1** step. | Designed and tested for long horizons (96-720 steps); linear models improve a lot with longer windows [D1]. | Used far outside the setting it was validated in. No source tests DLinear at 30-in, 1-out. |
| F4 | **No `naive_baseline.py`**, unlike `arima` and `chronos`. | On the one financial dataset tested, DLinear roughly tied "repeat last value" [D1]. | **The most important gap for this angle:** nothing checks whether it beats doing nothing. |
| F5 | Glossary says the source survey found DLinear "genuinely competitive on finance." | [D1]'s only financial result is roughly a tie with the naive baseline. | Overstated. "No worse than naive, sometimes slightly better" is what the evidence supports. |
| F6 | Trains 60 full-batch Adam steps at learning rate 0.01, fixed seed 42, no validation or early stopping. | -- | Reproducible (fixed seed), but `train_loss` is fit-to-history only and says nothing about forecast quality. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `forecast_price` | Predicted next close. (This angle really does name it `forecast_price` -- unlike `arima`, whose field is `forecast`.) |
| `forecast_return` | `(forecast_price - last_close) / last_close`. |
| `direction` | `up` if `forecast_return` > 0.0001 (0.01%), `down` if < -0.0001, else `flat`. |
| `last_close` | The last actual close the model saw. |
| `lookback` | Always `30`. |
| `n_train_windows` | How many 30-bar training examples it learned from (`n_observations - 30`). |
| `train_loss` | Final training error on normalized prices. **Not** a measure of forecast accuracy. |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Model trained and forecast produced. | All fields above. |
| `no_data` | No bars, or no `close` column. | Identification fields only. |
| `insufficient_data` | Fewer than 100 closes (default; overridable via `VINU_DLINEAR_MIN_OBSERVATIONS`), **or** fewer than 20 training windows. Both reasons share this one status. | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**Where DLinear comes from.** The 2022 paper "Are Transformers Effective
for Time Series Forecasting?" [D1] argued that large Transformer models
weren't actually earning their complexity on long-horizon forecasting,
and proposed "embarrassingly simple" linear models as a baseline. It had
three variants: plain Linear, NLinear (subtract the last value first, to
handle level shifts), and DLinear (split off the trend first). They beat
the Transformers on most of 9 benchmark datasets [D1].

**How DLinear works.** Take a window of past values. Run a moving average
over it -- that's the trend. Subtract the trend from the original --
that's the remainder (the paper calls it "seasonal"). Apply one linear
layer (a learned weighted sum) to each, add the two results: that's the
forecast [D1]. Nothing else -- no attention, no nonlinearity.

**What our code does.** Normalizes the ticker's closes (subtract the
average, divide by the standard deviation), cuts them into overlapping
30-bar windows each paired with the bar that followed, trains a fresh
DLinear on those for 60 steps, then feeds it the latest 30 bars to
predict the next one, and converts the prediction back to a price. Runs
on CPU on purpose -- the model is tiny, and a real out-of-memory crash on
a shared GPU was hit earlier (noted in the code).

**The padding bug (F1), in plain terms.** A 5-bar moving average needs 2
bars on each side of each point. At the very ends of the window there
aren't any, so something has to be made up. The reference code copies
the edge value [D2]; ours uses PyTorch's built-in padding, which fills
with zeros. Since prices are normalized, zero means "the historical
average price" -- so the trend at the latest 2 bars gets pulled toward
the long-run average. On a perfectly flat input, the last trend value
comes out 40% too low. It's a one-line fix, but it changes the model's
behavior, so it should be re-backtested after fixing.

**What the evidence really says about finance.** The paper's only
financial dataset is daily exchange rates. There, the trivial "repeat
the last value" forecast beat every Transformer by around 45%, and
DLinear essentially matched it -- tied at two horizons, slightly better
at two [D1]. That's consistent with prices being close to a random walk
(see `01-arima-angle.md`): the most a simple model can usually do is not
lose to "no change." The honest reading is "a cheap baseline that
doesn't fall below naive," not "competitive on finance."

**Why a naive baseline matters most here (F4).** `arima` and `chronos`
each ship with a `naive_baseline.py` so their backtests can show whether
they beat "no change." `dlinear` doesn't. Given R1, that comparison is
the single most informative thing this angle could report.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| D1 | Zeng, Chen, Zhang & Xu, "Are Transformers Effective for Time Series Forecasting?," arXiv:2205.13504, 2022 (full PDF, pp. 4-6) | DLinear design (moving-average decomposition + one linear layer each); helps "when there is a clear trend"; Table 2 Exchange-Rate MSEs for DLinear vs. Repeat; Repeat beats Transformers on Exchange-Rate by ~45%; linear models beat Transformers by 20-50% in most cases; longer look-back significantly boosts linear models. | https://arxiv.org/abs/2205.13504 |
| D2 | Reference implementation, `cure-lab/LTSF-Linear`, `models/DLinear.py` | Moving average pads by repeating first/last values (`padding=0` + manual repeat); default `kernel_size = 25`. | https://github.com/cure-lab/LTSF-Linear/blob/main/models/DLinear.py |
| -- | Direct test in the production container `vinu-components-initial-analysis-api-1`, torch 2.14.0 | Ran our `AvgPool1d(kernel_size=5, padding=2)` vs. the reference padding on a flat series of 1.0s: ours `[0.6, 0.8, 1.0, 1.0, 1.0, 0.8, 0.6]`, reference all `1.0`. | (local test, 2026-09-24) |

**Tried and not used:**
- PyTorch's `AvgPool1d` documentation page -- wouldn't render (redirect
  loop), so its padding behavior was confirmed by the direct test above
  instead.
