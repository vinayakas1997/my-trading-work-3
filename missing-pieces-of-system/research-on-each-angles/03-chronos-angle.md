# 03 — chronos

- **Angle id:** `chronos`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/chronos/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Chronos is Amazon's general-purpose forecasting model, pretrained on
many kinds of time series (not specifically stocks). It is shown the
last 512 closing prices and, without any training on this ticker,
predicts the next 5 bars as a range: a low (10th percentile), middle
(median) and high (90th percentile) estimate. It is a comparison
baseline, not a first-choice signal.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | **Zero-shot:** patterns learned from general time series transfer to this ticker without training on it. | [C1] |
| A2 | **Univariate:** only the price history matters -- no volume, news or other inputs. | [C3] |
| A3 | The series can be represented after **dividing by its average level and snapping each value to one of ~4,094 fixed bins**. Values outside the bin range are clipped. | [C3] |
| A4 | Enough context shows the trend: the model "tend[s] to underestimate the trend when the context is not sufficiently long" and "struggles with the exponential trend." | [C3] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Chronos-large, zero-shot, 512 past daily excess returns, global markets | Out-of-sample **R² = −1.37%** (worse than predicting the average) and directional accuracy **"just above 51%"**. Underperformed CatBoost/LightGBM. **Same model size and context length as our code.** | [C4] |
| R2 | Larger Chronos / wider context | Performance "gradually improves as the larger model and wider window size are used" -- but stays weak zero-shot. | [C4] |
| R3 | Fine-tuning general models on financial data vs. pretraining from scratch on it | Off-the-shelf models "perform poorly in zero-shot and fine-tuning settings"; models pretrained from scratch on financial data did substantially better. | [C4] |
| R4 | Chronos-Bolt vs. original Chronos | Model card: Bolt is "more accurate (5% lower error), up to 250 times faster and 20 times more memory-efficient." A newer **Chronos-2** is also listed. | [C2] |
| R5 | General benchmarks (not finance-specific) | "Comparable and occasionally superior zero-shot performance" to models trained on each dataset. | [C1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Uses `amazon/chronos-t5-large` (710M params), ~14s per call on CPU (measured in `compute.py`'s docstring). | Model card points to Chronos-Bolt (~250x faster, 5% lower error) and Chronos-2 [C2]. | **Worth switching.** Speed is this system's known bottleneck, and the newer model is also reported more accurate. Needs its own test before changing. |
| F2 | Feeds raw **closing prices** (price level). | Mean scaling + uniform bins over [-15, +15], ~4,094 tokens [C3]. | **Derived here, not stated in a source:** 30 ÷ 4,094 ≈ 0.0073, so one bin ≈ **0.73% of the average price**. Moves smaller than that often collapse into one bin. Most 1min/5min moves are smaller than 0.73%. This very likely explains why the code's own docstring reports p10/median/p90 "genuinely identical" on calm stocks. Chronos is likely weakest on our finest timeframes. |
| F3 | Price levels, not returns. | [C4]'s weak result (R1) was on **returns**. | Not a like-for-like comparison. Price levels have the precision problem in F2; returns wouldn't. Neither setup has been shown to work well. |
| F4 | If Chronos can't load, silently substitutes a **random-walk-with-drift proxy** and sets `model_backend: "fallback_proxy"`. | -- | A fallback row is **not Chronos at all**. The current glossary doesn't mention this. Any reader must check `model_backend` first. |
| F5 | `compute.py` hardcodes `closes[-512:]`; `backtest.py` uses `[-MIN_OBSERVATIONS:]`. | -- | Identical by default (512), but they diverge if `VINU_CHRONOS_MIN_OBSERVATIONS` is overridden. |
| F6 | Module docstring says the **tiny** (8M) checkpoint is used. | -- | Stale -- the code uses **large** (710M). |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `model_backend` | `"pretrained"` = real Chronos ran. `"fallback_proxy"` = **Chronos did not run**; the forecast is a random walk with drift. **Check this first.** |
| `fallback_reason` | Why the fallback was used; `null` when Chronos ran. |
| `checkpoint` | `"amazon/chronos-t5-large"`, or `null` on fallback. |
| `median_forecast` | List of 5 predicted prices, one per future bar (median of 64 sampled paths). |
| `p10_forecast` / `p90_forecast` | Lists of 5 prices: the low and high end of the range. Can be identical to the median on calm stocks (F2) -- that means "range too small to represent," not "certain." |
| `forecast_horizon` | Always `5` (bars ahead). |
| `last_close` | The last price the model saw. |
| `n_observations` | How many closing prices were available (only the last 512 are used). |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | A forecast was produced -- **by Chronos or by the fallback**; see `model_backend`. | All fields above. |
| `no_data` | No price bars supplied. | Identification fields only. |
| `insufficient_data` | Fewer than 512 closing prices (overridable via `VINU_CHRONOS_MIN_OBSERVATIONS`). | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What Chronos is.** A language model repurposed for numbers. Language
models predict the next word from a fixed vocabulary; Chronos turns a
number series into "words" by (1) dividing every value by the average
absolute value of the context window ("mean scaling"), then (2) placing
each scaled value into one of ~4,094 equal-width bins between -15 and +15
[C3]. It's a standard T5 transformer trained with ordinary cross-entropy
loss on a large collection of public time series plus synthetic series
generated from Gaussian processes [C1][C3]. It was trained with 512
steps of context and 64 steps of prediction [C3].

**How our code uses it.** Takes the last 512 closes, asks the model for 5
steps ahead with 64 sampled future paths, and reports the 10th, 50th and
90th percentile at each step. On CPU this is ~14s per call (plus a
one-time ~7s load) -- measured in the code, not from a source.

**Why the range sometimes has zero width (F2).** After dividing by the
average price, a stock trading around $180 becomes a series of values
all very close to 1.0. The bins are about 0.0073 wide in those units,
i.e. about 0.73% of the price. If the stock rarely moves 0.73% within the
window -- normal for 1min/5min bars on a large cap -- most of the
context lands in one or two bins, and so do the 64 sampled futures. The
10th, 50th and 90th percentiles can then all be the same bin. That's a
resolution limit of the method, not a claim of certainty. (This
explanation is derived from [C3]'s stated numbers; no source states it
for stocks specifically.)

**What the evidence says about stocks.** The closest real test [C4] used
the same large model and the same 512-step context on daily excess
returns across global markets: R² slightly negative and direction right
about 51% of the time -- essentially no usable signal zero-shot, and
worse than tree-based models. Bigger models and longer windows helped a
little. Fine-tuning general models didn't close the gap; models
pretrained from scratch on financial data did much better. That's the
evidence behind this angle being labeled "comparison baseline" rather
than "signal," and behind the Kronos angle (finance-specific) existing.

**The fallback.** If the package or weights can't load, the angle still
returns `status: "ok"`, but with a simple random-walk-with-drift
forecast and normal-distribution bands. That keeps the pipeline running,
but it means an "ok" Chronos row may contain no Chronos output at all.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| C1 | Ansari et al., "Chronos: Learning the Language of Time Series," arXiv:2403.07815, 2024 (abstract page) | Scaling + quantization into a fixed vocabulary; T5 trained with cross-entropy; public + synthetic Gaussian-process data; comparable/occasionally superior zero-shot results on general benchmarks. | https://arxiv.org/abs/2403.07815 |
| C2 | Hugging Face model card, `amazon/chronos-t5-large` | 710M parameters; sampling multiple trajectories; Chronos-Bolt "5% lower error, up to 250 times faster, 20 times more memory-efficient"; newer `amazon/chronos-2` available. | https://huggingface.co/amazon/chronos-t5-large |
| C3 | Same paper as C1, full HTML text | Mean scaling (divide by mean absolute value of context); uniform bins in [-15, +15], vocabulary 4,096 incl. PAD/EOS; context 512, prediction 64 in training; univariate only; range clipping; underestimates trend with short context; struggles with exponential trend. | https://arxiv.org/html/2403.07815 |
| C4 | Rahimikia, Ni & Wang, "Re(Visiting) Time Series Foundation Models in Finance," arXiv:2511.18578, 2025 (full HTML text) | Chronos tiny→large tested; Chronos-large with 512 past daily excess returns: R² −1.37%, directional accuracy just above 51%; weaker than CatBoost/LightGBM; improves with size/window; from-scratch financial pretraining did much better. | https://arxiv.org/html/2511.18578v1 |

**Tried and not used:**
- Marconi (2025), "Time Series Foundation Models for Multivariate
  Financial Time Series Forecasting," arXiv:2507.07296 -- read, but its
  positive results are for a different model (TTM) on Treasury yields,
  FX volatility and spreads, not Chronos on stock prices.
