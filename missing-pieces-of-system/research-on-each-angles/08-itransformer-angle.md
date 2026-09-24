# 08 — itransformer

- **Angle id:** `itransformer`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/itransformer/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

A small transformer trained from scratch on this ticker every run. It
does **not** attend across other tickers -- despite the name's promise
of cross-asset correlation -- it attends across this **one symbol's own
OHLCV channels** (open/high/low/close/volume), treating each channel's
whole lookback window as one token. Forecasts one step ahead for every
channel; direction is read from the close channel.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Embedding a **whole variate's lookback window** as one token (not per-timestep tokens), then running self-attention across those variate-tokens, lets the model learn correlations between variates directly. | [I1] |
| A2 | This "inverted" tokenization fixes a real weakness of plain time-token transformers: mixing several variates into one per-timestep token "fuses multiple variates ... which may fail in learning variate-centric representations." | [I1] |
| A3 | *(Code's own explicit assumption, not the paper's)* Applying the same variate-token mechanism to a single symbol's **OHLCV channels** (5 variates) is a genuine instance of the method's core idea, standing in for true cross-*asset* attention which the per-symbol `compute()` interface has no data for. | code's own documented deviation |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | 8-currency **Exchange-Rate** dataset (the one financial-ish benchmark in the paper), lookback 96, averaged across horizons | iTransformer MSE **0.360**; **DLinear 0.354** -- the plain linear baseline edges it out. PatchTST 0.367, RLinear 0.378. Exchange is the one major benchmark in the paper where a linear model beats iTransformer. | [I2] |
| R2 | Ablation: attention across variates vs. a plain feed-forward network on each dimension, by dataset variate-count | The benefit of cross-variate attention grows with the **number of variates** -- large on Traffic (862 variates), much smaller on datasets with few variates. | [I2] |
| R3 | General benchmark comparison, many long-horizon datasets | iTransformer reaches state-of-the-art, crediting the "variate-centric" representation for better capturing multivariate correlations than time-token transformers. | [I1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Uses 5 channels (open/high/low/close/volume) as the "variates." | Cross-variate attention's benefit scales with variate count -- large gains needed many variates (862 for Traffic), much smaller with few [I2]. | **The architecture is applied exactly where the paper's own ablation says it matters least.** With only 5 highly-correlated OHLCV channels (open/high/low/close move almost in lockstep for any one bar), there's very little cross-variate structure left to discover -- unlike the paper's real use case (many genuinely distinct sensor/traffic/economic series). This compounds the already-documented channels-not-tickers substitution: even if it *were* attending across real tickers, 5 is a small variate count by the paper's own standard. |
| F2 | The variate-token design -- whole lookback window embedded as one token per channel, attention across channel-tokens -- matches the paper's actual mechanism. | Confirmed: "each time series ... is firstly tokenized ... Embedding: R^T -> R^D" applied to the whole series per variate [I2]. | **Architecturally faithful**, as far as the mechanism itself goes (channels standing in for variates). The deviation is entirely about *what* fills the variate slot (channels vs. tickers), not *how* attention is applied -- exactly as the code's own docstring claims, verified against the paper's formulation. |
| F3 | Reports a forecast for **every** channel (`forecast_open/high/low/close/volume`), not just close. Code comment says this fixes an earlier version that computed all 5 internally but discarded 4 of them. | -- (internal fix, code-only) | Sensible -- the model already produces all 5 for free in its forward pass; discarding them was pure waste. No literature question here. |
| F4 | Only the one financial-ish result available (Exchange-Rate, R1) shows iTransformer **losing to DLinear**, which `04-dlinear-angle.md` already found roughly *tying* the naive baseline on the same dataset. | Same [I2] table. | **Chain of evidence**: naive ≈ DLinear > iTransformer on the one financial series tested in either paper. Nothing in the published record shows iTransformer beating a "do nothing" forecast on financial data -- consistent with `naive_baseline.py` existing here specifically to check that, per-ticker. |
| F5 | `n_channels`/`channels` fields report which of the 5 were actually available and used (falls back to `["close"]` if only close exists). | -- | Honest self-reporting -- a caller can see when cross-variate attention degenerated to a single variate (no attention benefit possible at all). |
| F6 | `MIN_BARS` raised to the shared `DEFAULT_MIN_OBSERVATIONS` (100), consistent with the other neural-net angles. | -- (internal decision) | Consistent with `arima`/`dlinear`/`exponential_smoothing`/`garch`; no new finding. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `forecast_price` | Alias for `forecast_close` -- the primary one-step-ahead forecast. |
| `forecast_open` / `forecast_high` / `forecast_low` / `forecast_close` / `forecast_volume` | One-step-ahead forecast for each channel that was available and used. |
| `forecast_return` | `(forecast_price - last_close) / last_close`. |
| `direction` | `up`/`down`/`flat`, thresholded from `forecast_return` at ±0.01%. |
| `last_close` | Last actual close the model saw. |
| `lookback` | Always `32`. |
| `channels` | Comma-separated list of channels actually used (subset of open/high/low/close/volume). |
| `n_channels` | How many channels were used -- the effective "variate count" for this run (see F1/F5). |
| `n_train_windows` | How many 32-bar training examples it learned from. |
| `train_loss` | Final training MSE across all channels combined -- **not** forecast accuracy. |
| `n_observations` | How many bars were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Model trained and forecast produced. | All fields above. |
| `no_data` | No bars, or no `close` column. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_BARS` (100) bars, **or** fewer than 20 training windows after windowing -- both reasons share this one status (mirrors `dlinear`'s same two-reasons-one-status pattern). | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**Where iTransformer comes from, and what it actually inverts.** Standard
transformer forecasters take one timestamp's readings across all
variates and pack them into a single token, then run attention across
*time steps*. iTransformer flips this: it takes one variate's *entire*
lookback window and embeds it as a single token, then runs attention
across *variates* instead of across time, letting a lightweight
per-token feed-forward network handle the temporal structure inside
each token [I1][I2]. The stated motivation is that mixing several
variates into one per-timestep token can "fail in learning
variate-centric representations" [I1] -- attention across time steps
can't easily tell the model "the trend in variate A predicts the trend
in variate B" the way attention across variate-tokens can.

**What our code's variate slot actually holds.** The paper's real use
case is genuinely different series -- traffic sensors, exchange rates
between different currency pairs, weather stations. Our code's own
docstring is upfront that it substitutes this one symbol's OHLCV
*channels* for that role, because `compute()` is called per-symbol with
no sibling-ticker data available, and states plainly this "does not
capture true cross-*asset* correlation." Verified against the paper: the
substitution is honest about the mechanism (F2) but doesn't address a
deeper problem the paper's own ablation surfaces (F1) -- open, high,
low, close and volume aren't 5 richly independent signals the way
traffic sensors or currency pairs are; open/high/low/close in particular
move almost together within any bar. The paper found cross-variate
attention's payoff scales with genuinely distinct variate count, and 862
(Traffic) is a very different regime from 5 (this angle).

**What the one financial result says.** Exchange-Rate is the paper's
only currency/financial-style dataset, and it's the one dataset where a
plain linear model (DLinear) beat iTransformer [I2] -- and
`04-dlinear-angle.md` already found DLinear itself only roughly ties
"repeat the last value" on that same dataset. Put together: on the
single closest-to-financial benchmark either paper reports, the order
is naive ≈ DLinear > iTransformer. That doesn't mean iTransformer can't
work on a given ticker's own OHLCV -- this angle's own `naive_baseline.py`
exists precisely to check that per-run -- but the published record gives
no reason to expect it beats "do nothing" on price data by default.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| I1 | Liu, Hu, Zhang, Wu, Wang, Ma & Long, "iTransformer: Inverted Transformers Are Effective for Time Series Forecasting," arXiv:2310.06625, ICLR 2024 (abstract page) | Core idea: tokenize whole variate series, attend across variate-tokens instead of time-tokens; stated motivation (per-timestep tokens fuse multiple variates and fail to learn variate-centric representations); state-of-the-art claim on real-world multivariate benchmarks. | https://arxiv.org/abs/2310.06625 |
| I2 | Same paper, full HTML text | Confirmed variate-token = whole lookback window per variate (embedding R^T -> R^D applied per variate); Table 1 Exchange-Rate MSEs (iTransformer 0.360, DLinear 0.354, PatchTST 0.367, RLinear 0.378); ablation showing cross-variate attention's benefit scales with variate count (large for Traffic's 862 variates, smaller for low-variate-count datasets). | https://arxiv.org/html/2310.06625 |
