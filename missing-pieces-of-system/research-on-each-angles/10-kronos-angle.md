# 10 — kronos

- **Angle id:** `kronos`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/kronos/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`,
  vendored model code in `_kronos_model/`, MIT license, from
  `github.com/shiyu-coder/Kronos`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

Kronos is a foundation model built specifically for financial K-line
(candlestick) data -- pretrained on 12B real records from 45 exchanges,
unlike the general-purpose `chronos`/`timesfm` comparison baselines. It
tokenizes OHLCV bars and autoregressively predicts the next several
bars' full OHLC. This system's closest thing to a "first-choice"
deep-learning signal. **Check `model_backend` first** -- `"fallback_proxy"`
means the real model didn't load and a much weaker substitute ran instead.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | Financial K-line sequences can be discretized into hierarchical tokens and modeled autoregressively, the same way language models handle text. | [KR1] |
| A2 | Pretraining on 12B real K-lines across 45 exchanges (China, US, Japan, India, Korea, Hong Kong, crypto, forex) lets the model transfer to a new ticker without training on it (zero-shot). | [KR1] |
| A3 | Multiple sampled forecast paths, averaged, give a better point estimate than a single greedy sample. | [KR2] |
| A4 | Input length should not exceed the model's trained context (512 bars for the `base`/`small` checkpoints) for best performance. | [KR2] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Price forecasting, RankIC, across in-distribution stock markets (China, US, Japan, India, Korea, Hong Kong) | Kronos improves RankIC by **93% over the leading general-purpose time-series foundation model** and **87% over the best non-pretrained baseline** tested. | [KR1] |
| R2 | Volatility forecasting, vs. GARCH/ARCH and deep baselines (iTransformer, TimeMOE, Chronos, etc.) | **9% lower MAE** than the best baseline. | [KR1] |
| R3 | Model size table | `small` = 24.7M params, `base` = 102.3M, `large` = 499.2M -- all three share the same tokenizer and 512-bar max context. A separate `mini` (4.1M) uses a **different** tokenizer (`Kronos-Tokenizer-2k`) with a longer 2048-bar context. | [KR2] |
| R4 | Evaluation lookback windows used in the paper, by bar frequency | Ranged from **40 bars for daily data up to 480 bars for 5-minute data** -- shorter timeframes were given much more context in the paper's own evaluation. | [KR1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | Downloads and pairs `NeoQuasar/Kronos-base` (102.3M params) with `NeoQuasar/Kronos-Tokenizer-base`. | `base` and `small` share `Kronos-Tokenizer-base` (512-bar context); `mini` requires the *different* `Kronos-Tokenizer-2k` [KR2]. | **Correct pairing**, verified against the model card's own table -- an easy mistake to make (pairing the wrong tokenizer with `mini`) that this code doesn't make. |
| F2 | `KronosPredictor(..., max_context=512)`, and the full `bars` DataFrame (however long) is passed straight to `predictor.predict(df=df, ...)` with no manual truncation in `compute.py`/`_fit_and_forecast`. | Model card recommends input length not exceed 512 [KR2]. | **Not a live truncation bug**, verified by reading the vendored inference code directly: `auto_regressive_inference` in `_kronos_model/kronos.py` internally slides a `max_context`-sized window (`start_idx = max(0, initial_seq_len - max_context)`) regardless of how much history is handed in. Feeding more than 512 bars is safe -- the extra history is simply not used, silently. |
| F3 | Sampling: `T=0.8, top_k=0, top_p=0.9, sample_count=3`. | Repo's own documented example: `T=1.0, top_p=0.9, sample_count=1`; `sample_count>1` means paths are generated and **averaged** [KR2]. | Lower temperature (0.8 vs. the example's 1.0) biases sampling toward the model's more likely tokens -- a reasonable, deliberate-looking choice for a point forecast, but it's an undocumented deviation from the repo's own example, not something stated as "recommended" anywhere read. `sample_count=3` matches the documented averaging behavior correctly. |
| F4 | `MIN_OBSERVATIONS` defaults to **30** (not raised to the shared `DEFAULT_MIN_OBSERVATIONS=100` the other classical/DL angles got), so the live gate is `30 + CONTEXT_WINDOW(32) = 62` bars minimum, across every timeframe including `1min`/`5min`. | The paper's own evaluation used **480 bars of context specifically for 5-minute data** (and even 40 for daily) [KR1, R4]. | **Real, unverified gap.** At intraday timeframes this angle can run on roughly an eighth of the context the model was actually *evaluated* with in its own paper. That doesn't necessarily mean a bad forecast (the model can accept less), but nothing in this codebase checks that 62 bars is enough to be meaningful at 1min/5min specifically -- unlike `chronos`, whose 512-bar minimum happens to match its own training context exactly. |
| F5 | Module docstring summarizes sizes as "Kronos-mini 4M -> Kronos-large 499M params." | Real table has **four** sizes, not two endpoints, and `mini` isn't on the same tokenizer/context axis as the others [KR2]. | Minor inaccuracy in the comment -- the actual downloaded/used checkpoint (`base`, 102.3M) sits in the middle and is never named in that range statement, which could read as "somewhere between two extremes" without saying which. Doesn't affect behavior, only documentation clarity. |
| F6 | Fallback: a fresh 1-hidden-layer, 8-unit MLP trained on 60 Adam steps over the ticker's own last `CONTEXT_WINDOW=32` bars, predicting next-bar O/H/L/C log-returns. Clearly labeled `model_backend: "fallback_proxy"` with a reason string. | -- | **Honest and well-labeled** -- same posture as `chronos`'s fallback (F4 in [03-chronos-angle.md](03-chronos-angle.md)), but Kronos's fallback is explicitly acknowledged in its own comment as "no zero-shot cross-market generalization," i.e. this reduces the flagship finance model to something weaker than several of the other classical angles when it fires. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `model_backend` | `"pretrained"` = real Kronos ran. `"fallback_proxy"` = the small MLP substitute ran instead. **Check this first.** |
| `fallback_reason` | Why the fallback fired; `null` when the real model ran. |
| `checkpoint` | `"NeoQuasar/Kronos-base"` when pretrained; absent on fallback. |
| `context_window` | `512` when pretrained (the model's real max context); `32` on fallback (the MLP's tiny window). |
| `predicted_next_open/high/low/close` | The next bar's forecast OHLC. |
| `forecast_horizon` | Number of future bars forecast (real model: `5`; not present on fallback, which only predicts 1 bar). |
| `forecast_ohlc` | Real-model-only: full 5-step OHLC arrays, one value per future bar per channel. |
| `last_close` | The last actual close the model saw. |
| `n_observations` | How many bars were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | A forecast was produced -- **by Kronos or the fallback**; see `model_backend`. | All fields above. |
| `no_data` | No bars supplied. | Identification fields only. |
| `insufficient_data` | Missing OHLC columns, or fewer than `MIN_OBSERVATIONS + CONTEXT_WINDOW` (62 by default) bars. | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What Kronos is, and how it differs from Chronos.** Both tokenize
numeric series and run an autoregressive transformer over the tokens,
but Kronos is trained specifically and only on financial K-line data
(12B records, 45 exchanges) rather than general time series, and its
tokenizer is built around OHLCV structure rather than a generic
mean-scaled bin scheme [KR1]. The paper's own framing is that
general-purpose foundation models "often underperform specialized,
non-pre-trained models" on financial tasks -- exactly the gap Kronos
is built to close, and exactly why the glossary calls it the
"first-choice" deep-learning angle versus `chronos`/`timesfm` as
baselines.

**Why the checkpoint choice is correct (F1).** The model ships in four
sizes, and mixing up the tokenizer would silently corrupt every
forecast. `mini` uses a wider context (2048) with its own tokenizer;
`small`/`base`/`large` share one 512-context tokenizer. This code
downloads exactly the matched pair for `base` -- verified against the
model card's own table, not assumed from the code comment alone.

**Why passing the full bars DataFrame is safe (F2).** It would be easy
to assume the caller must manually slice to 512 bars before calling
`predict()`. Reading the vendored inference loop directly shows it
already does this internally via a sliding context window, so
`compute.py` handing it arbitrarily more history than 512 bars doesn't
error or silently misbehave -- it's simply ignored beyond the most
recent `max_context` bars, exactly as the model card's "does not
exceed this limit" guidance implies should happen.

**The context-length question the paper itself raises but the code
doesn't check (F4).** The paper didn't evaluate Kronos with a single
fixed lookback -- it varied lookback by bar frequency, using far more
context at 5-minute resolution (480 bars) than daily (40). This angle
uses one fixed minimum (62 bars total) across every timeframe. That's
not necessarily wrong -- the model can run on less -- but it means the
intraday runs of this angle operate in a context regime well below what
the paper's own evaluation used to produce its reported RankIC/MAE
numbers, and nothing here measures whether that matters for this
codebase's actual tickers and timeframes.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| KR1 | "Kronos: A Foundation Model for the Language of Financial Markets," AAAI 2026 / arXiv:2508.02739 (full HTML text) | Tokenizer + autoregressive transformer design; 12B K-line pretraining across 45 exchanges; Table 1 model sizes (small/base/large parameter counts, shared tokenizer/context); Table 8 per-frequency evaluation lookback windows (40 bars daily to 480 bars 5-min); RankIC (+93%/+87%) and volatility MAE (-9%) results; asset universe (China/US/Japan/India/Korea/Hong Kong stocks, crypto, forex) and baselines (GARCH, ARCH, iTransformer, TimeMOE, Chronos). | https://arxiv.org/html/2508.02739 |
| KR2 | Hugging Face model card, `NeoQuasar/Kronos-base`, and GitHub repo `shiyu-coder/Kronos` README | Full model-size table incl. `mini` (4.1M, `Kronos-Tokenizer-2k`, 2048 context) vs. `small`/`base`/`large` (`Kronos-Tokenizer-base`, 512 context); recommended input length guidance; example inference call (`T=1.0, top_p=0.9, sample_count=1`); confirmation that `sample_count>1` generates and averages multiple paths. | https://huggingface.co/NeoQuasar/Kronos-base , https://github.com/shiyu-coder/Kronos |
| -- | Direct read of the vendored inference code, `vinu_initial_analysis/angles/kronos/_kronos_model/kronos.py`, `auto_regressive_inference()` | Confirmed the sliding-window context truncation (`start_idx = max(0, initial_seq_len - max_context)`) runs regardless of how much history the caller passes in. | (local code read, 2026-09-24) |
