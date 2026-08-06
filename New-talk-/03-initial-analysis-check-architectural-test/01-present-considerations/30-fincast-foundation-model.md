---
name: fincast-foundation-model
status: candidate-not-implemented
purpose: reference note on FinCast, a second financial time-series foundation model found via web search Aug 2026 — an alternative to Kronos in the same category. Moved here from 03-claude-new-methods/ — borderline on Final-implementation limitation #2 (fits at fp16 ~2GB, fails at fp32 ~4GB); survives limitation #1 (not an LLM).
---

# FinCast — A Second Financial Time-Series Foundation Model

## Title / what it is

A foundation model for financial time-series forecasting, presented at ACM
CIKM 2026 — in the same category as Kronos (`09-kronos.md`): pretrained on
financial time-series data, usable zero-shot or fine-tuned per market.

## Explanation — how it works

Same general family as Kronos and the other TSFMs already catalogued
(`10-chronos.md` through `17-patchformer.md`) — a transformer/tokenizer-based
model pretrained on a large corpus of financial time-series data, producing
forecasts or embeddings usable across markets without per-ticker training.
Detailed architecture specifics weren't captured by the search beyond its
positioning as a Kronos-class foundation model.

## Input

A historical window of price data for a single series — context length
1024 for high-frequency series (seconds to daily), reduced to 256 for
coarser frequencies (weekly to monthly).

## Output format

A financial time-series forecast, generated autoregressively by the
decoder-only MoE transformer — same general output shape as Kronos
(`09-kronos.md`), point and/or distributional depending on configuration;
not independently confirmed which.

## Impact — what can be extracted

A second candidate for the `kronos_forecast`-style future angle. Worth
comparing against Kronos on this project's own tickers (AAPL/TSLA/JNJ)
before assuming Kronos is the only or best option — Kronos's own caveat
(benchmarks are MSE/CRPS, not economic; directional accuracy near 50%)
likely applies here too and should be checked, not assumed away because
it's newer.

## Is it LLM-dependent?

No — this is a time-series foundation model (transformer/tokenizer-based on
numeric K-line data), not an LLM in the text-generation sense, same category
as Kronos/Chronos/TimesFM already documented.

## Model size / base model (from source)

Explicitly stated: **FinCast is a decoder-only, sparse Mixture-of-Experts
(MoE) transformer with 1 billion parameters**, 4 experts per MoE layer with
top-k=2 routing. Training context length: 1024 for high-frequency series
(seconds to daily), reduced to 256 for coarser frequencies (weekly to
monthly). Baselines it's compared against in the paper: Google's TimesFM
(`11-timesfm.md`, 200M and 500M variants), Amazon's Chronos-T5
(`10-chronos.md`, small/base/large), and TimesMOE (large).

**Borderline on limitation #2**: ~2GB at fp16 (passes), ~4GB at fp32
(fails) — confirm serving precision before counting on this one.

This makes FinCast roughly **2×–5× larger than Kronos-large** (499M, per
`09-kronos.md`) at a single fixed size, whereas Kronos instead ships a
mini-to-large range (4M–499M) — worth factoring into any head-to-head
comparison, since a bigger model isn't automatically the better choice
given the shared caveat about directional accuracy vs. statistical
benchmarks.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Direct alternative to Kronos (`09-kronos.md`) — same role, different
model, worth a side-by-side comparison rather than picking one on
reputation alone.

## Source

- [FinCast: A Foundation Model for Financial Time-Series Forecasting](https://dl.acm.org/doi/10.1145/3746252.3761261) — ACM CIKM 2026
- [FinCast (arXiv preprint)](https://arxiv.org/abs/2508.19609) — `arXiv:2508.19609`
