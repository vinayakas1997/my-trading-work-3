# 26 — tips_regime_aware_transformer

- **Angle id:** `tips_regime_aware_transformer`
- **Cluster:** B — Deep-learning / foundation-model forecasts
- **Code:** `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/tips_regime_aware_transformer/`
  (`compute.py`, `backtest.py`, `naive_baseline.py`, `spec.yaml`)
- **Researched:** 2026-09-24. Every source in [Citations](#8-citations)
  was opened and read during this research, not recalled from memory.

---

## 1. Short definition  *(passed to the LLM)*

A small transformer trained from scratch on this ticker, self-detecting
momentum vs. mean-reversion regime via lag-1 return autocorrelation, and
routing to one of two regime-specific output heads. **The name cites a
real 2026 paper, but this implementation shares almost no mechanism with
it** -- see F1, the strongest architecture-fidelity gap found in this
whole research folder. Glossary already correctly warns "TIPS" here is
an internal codename, not the Treasury bond.

## 2. Assumptions  *(passed to the LLM)*

| id | Assumption | Source |
|---|---|---|
| A1 | *(Real TIPS)* Regime-adaptive forecasting behavior can emerge from **knowledge distillation** across several "bias-specialized teacher" transformers (each encoding a distinct temporal prior -- causality, locality, periodicity, via attention masking and patching), **without needing any explicit regime label or routing decision** built into the architecture. | [TP1] |
| A2 | *(Code's own design)* Lag-1 return autocorrelation, computed over a trailing window, is a valid real-time signal for whether a ticker is currently in a momentum or mean-reversion regime, and can be used to **explicitly gate** which of two output heads produces a forecast. | code's own design |
| A3 | *(Real TIPS)* Many time-series transformers implicitly assume stationarity, an assumption "routinely violated in financial markets characterized by regime shifts" -- and state-of-the-art time-series transformers can underperform even vanilla transformers on financial tasks, while simpler CNN/RNN architectures with distinct inductive biases sometimes do better with far less complexity. | [TP1] |

## 3. Assumption results  *(passed to the LLM)*

| id | Setting | Reported result | Source |
|---|---|---|---|
| R1 | Real TIPS student vs. strongest teacher ensemble, four equity markets (CSI300, CSI500, NI225, **SP500**) | Average annual return 0.907, Sharpe 1.454, Calmar 1.934 -- "TIPS improves [annual return] by 54.8% and [Sharpe] by 8.8%" over the strongest ensemble baseline, at roughly **7x lower inference cost** (0.810 GFLOPs vs. 6.032 GFLOPs for the full teacher ensemble). | [TP1] |
| R2 | How regime-adaptive behavior actually arises in real TIPS | Emerges from analysis of the trained student's behavior (Section 5.2 of the paper) -- a consequence of the distillation process, not a designed-in routing mechanism. | [TP1] |

## 4. How our code compares to the literature

| id | What our code does | What the sources say | Verdict |
|---|---|---|---|
| F1 | One shared transformer encoder, **two hand-built output heads** (`momentum_head`, `mean_reversion_head`), selected per-sample via `torch.where` on an explicitly-computed lag-1-autocorrelation sign. No distillation, no teacher models, no bias-specific attention masks. | Real TIPS is a **two-stage knowledge-distillation framework**: seven bias-specialized teacher transformers (causal-mask and reverse-causal-mask for causality; overlapping-patch and ALiBi-decay for locality; fixed-period and learnable relative-position bias for periodicity), then a compact student distilled from their soft-averaged logits via low-temperature distillation, label smoothing, and stochastic weight averaging [TP1]. Its regime-awareness is explicitly framed as something that emerges *without* needing "explicit regime labels or routing decisions." | **The most severe architecture-fidelity gap found in this research folder.** This isn't a simplified or partial version of TIPS the way `lpatchtst` is a simplified (parallel, not sequential) version of its cited paper -- it implements a structurally unrelated mechanism (hand-computed regime statistic + hard head-routing) that the real paper's own framing treats as the *alternative* to what TIPS actually does. There is no teacher-student distillation anywhere in this code, no causality/locality/periodicity-specialized sub-models, and no soft-target training. |
| F2 | The two "regimes" this angle detects are strictly binary: momentum vs. mean-reversion, from one statistic (lag-1 autocorrelation sign). | Real TIPS's inductive priors span three genuinely different structural axes (causality, locality, periodicity), not one momentum/reversion split -- and 7 teachers, not 2. | Consistent with F1: even setting distillation aside, the *number and kind* of "regimes"/priors modeled don't correspond to the source design at all. |
| F3 | This angle's cited real financial evaluation (R1) includes SP500 -- genuine US equity index data, unlike most of Cluster B's angles researched so far (`dlinear`/`itransformer`/`patchtst`/`moment` all lacked or explicitly excluded real financial results). | -- | **A real irony worth naming plainly**: TIPS is one of the *few* architectures in this cluster with substantial, real, positive equity-market evaluation results -- but because this implementation doesn't share its mechanism, those results provide no evidence about what this angle's code actually does. The citation is to a real, relevant, well-evaluated paper; the code just isn't an implementation of it. |
| F4 | Regime detection and labeling logic itself (`_rolling_autocorr_lag1`, index alignment between `returns` (length n-1) and `close` (length n)) is careful and internally correct -- verified by hand-tracing the off-by-one padding (`np.concatenate([[np.nan], autocorr])`) against how `_make_windows` consumes `regime_labels_by_close_idx`. | -- (internal correctness check, code-only) | The regime-detection *mechanism this code actually uses* (however unrelated to the cited paper) is implemented without an indexing bug -- worth confirming directly rather than assuming, since off-by-one errors in this kind of lagged-alignment code are common. |

## 5. Output fields  *(passed to the LLM -- from `compute.py`, not the internet)*

| Field | Meaning |
|---|---|
| `forecast_price` | One-step-ahead predicted close. |
| `forecast_return` | `(forecast_price - last_close) / last_close`. |
| `direction` | `up`/`down`/`flat`, thresholded at ±0.01%. |
| `regime` | `"momentum"` or `"mean_reversion"` -- the detected regime for the most recent window (see F1/F2 for what this mechanism actually is vs. what the name suggests). |
| `regime_autocorr` | The underlying lag-1 autocorrelation statistic behind the regime label. |
| `n_momentum_windows` / `n_mean_reversion_windows` | How many of the training windows fell into each regime -- lets a reader see the regime mix the two heads were actually trained on. |
| `last_close` | Last actual close the model saw. |
| `lookback`, `regime_window` | Always `24` and `20` respectively. |
| `n_train_windows` | How many windows survived filtering. |
| `train_loss` | Final training MSE -- fit quality, not forecast accuracy. |
| `n_observations` | How many closes were supplied. |
| `symbol`, `analysis_at`, `angle` | Identification. |

## 6. Status values  *(passed to the LLM -- from `compute.py`)*

| `status` | Meaning | Fields present |
|---|---|---|
| `ok` | Model trained and forecast produced. | All fields above. |
| `no_data` | No bars, or no `close` column. | Identification fields only. |
| `insufficient_data` | Fewer than `MIN_BARS` (120) bars, **or** fewer than 20 usable windows after regime-label filtering -- both reasons share this one status (same pattern as `dlinear`/`itransformer`/`lpatchtst`/`lstm`/`patchtst`/`tft`). | + `n_observations`. |

## 7. Comprehensive explanation  *(for humans only)*

**What real TIPS actually is.** A knowledge-distillation framework, not
a single model with a regime switch. Seven "teacher" transformers are
each trained to encode one specific inductive bias -- causal-only
attention, reverse-causal attention, overlapping temporal patches,
ALiBi distance-decayed attention, a fixed periodic bias, and a learnable
relative-position bias -- sharing one backbone architecture but differing
in their structural masks. A compact "student" model is then distilled
from the soft-averaged logits of all seven teachers, using
low-temperature distillation (to preserve fine-grained ranking signal),
aggressive label smoothing, and stochastic weight averaging [TP1]. The
paper's own analysis (not its architecture) finds that this distilled
student's behavior aligns differently with different priors depending on
market regime -- an *emergent* property of the distillation process, not
something wired in by an explicit regime detector.

**Why this code's mechanism is something else entirely (F1).** What's
actually implemented here is a completely different, much older idea:
compute one hand-picked statistic (lag-1 autocorrelation) to label the
current window as one of two regimes, then route the forecast through
whichever of two linear heads matches that label. This is a reasonable,
understandable design in its own right -- explicit regime-conditional
modeling is a real and common technique -- but it isn't TIPS. There's no
teacher ensemble, no distillation, no causality/locality/periodicity
priors, and only two regimes instead of the real method's richer,
multi-axis prior space.

**Why this matters for how the output should be weighed.** Because the
real TIPS paper has substantial, credible financial-market results --
including SP500, not just an excluded or weak Exchange-Rate afterthought
like several other Cluster B angles -- a reader could reasonably assume
this angle inherits some of that evidence. It doesn't: the mechanism
that produced those numbers isn't the mechanism running here. This
angle's own output should be judged on its own (much simpler,
unvalidated) regime-gated-heads design, not on the cited paper's
results.

**What's still solid.** The regime-detection and window-alignment logic
this code *does* implement was checked by hand and is internally
consistent -- the lag-1 autocorrelation, its index alignment against
`close`, and the `torch.where`-based head routing all do what the code's
own comments claim, even though what they claim to be replicating is a
different thing.

## 8. Citations

| id | Source | What was used | Link |
|---|---|---|---|
| TP1 | "Integrating Inductive Biases in Transformers via Distillation for Financial Time Series Forecasting" (TIPS), arXiv:2603.16985, 2026 (full HTML text) | Two-stage teacher-student distillation design; seven bias-specialized teachers (causal/reverse-causal masks, overlapping-patch/ALiBi locality biases, fixed-period/learnable-relative-position periodicity biases); soft-target distillation with label smoothing and SWA; regime-dependent alignment as an emergent, not explicitly-routed, property; Table 4 results (CSI300/CSI500/NI225/SP500 average annual return 0.907, Sharpe 1.454, Calmar 1.934); +54.8% AR / +8.8% SR over the strongest ensemble baseline at ~7x lower inference cost. | https://arxiv.org/html/2603.16985v1 |
