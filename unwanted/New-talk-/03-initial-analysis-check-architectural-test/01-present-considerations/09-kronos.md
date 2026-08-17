---
name: kronos
status: candidate-not-implemented
purpose: reference note on Kronos, the flagship open-source financial K-line foundation model. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 1 into its own file. Survives both Final-implementation limitations (no LLM, all sizes 4M-499M well under the 2-3GB cap).
---

# Kronos — The Flagship Financial K-Line Foundation Model (AAAI 2026)

## Title / what it is

The first open-source foundation model trained *only on financial K-lines*.
Pre-trained on **12 billion K-line records from 45 global exchanges** across
7 time granularities.

## Explanation — how it works

A specialized tokenizer discretizes OHLCVA (open/high/low/close/volume/
amount) into hierarchical tokens → an autoregressive decoder-only
Transformer predicts the next K-line (like GPT predicts the next word).

## Input

A historical **window/sequence of K-line bars** for a single ticker
(context length 512–2048 tokens/bars, per model variant) — not a single
bar, and not multiple tickers jointly.

## Output format

A predicted next K-line (forecast OHLCVA values) generated
autoregressively, or a full synthetic K-line sequence for generative use;
evaluated via RankIC/MAE/CRPS, not accuracy — it does not natively output
a simple "buy/sell" signal, that would need a downstream decision layer.

## Impact — what can be extracted

- +93% RankIC over the leading time-series foundation model (TSFM)
- +87% over the best non-pretrained baseline
- −9% MAE in volatility forecasting
- +22% generative fidelity for synthetic K-line sequences
- Zero-shot works across unseen markets; fine-tuning improves further

**The critical caveat** (independent review): benchmarks are **MSE/CRPS —
statistical, not economic**. Directional accuracy is barely above 50% in
general. Trained on noise-rich data, it may learn "the shape of noise, not
exploitable alpha." Its most defensible value today: **synthetic data
generation + zero-shot forecasts** — not a live-trading signal yet.

## Is it LLM-dependent?

No — a time-series foundation model (transformer/tokenizer-based on numeric
K-line data), not an LLM in the text-generation sense.

## Model size / base model

**Kronos-mini (4M params) → Kronos-large (499M)**, all on HuggingFace
(NeoQuasar). Context 512–2048. All variants comfortably fit under the 2-3GB
footprint cap (Kronos-large ≈ 1GB at fp16).

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Maps to a new `kronos_forecast`-style angle (price prediction) in
`vinu-initial-analysis`. Also the benchmark other price-only foundation
models (`10-chronos.md`, `11-timesfm.md`, `30-fincast-foundation-model.md`)
should be compared against.

## Source

- Kronos: AAAI 2026, `arXiv:2508.02739`, github.com/shiyu-coder/Kronos
