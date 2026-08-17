---
name: lag-llama
status: candidate-not-implemented
purpose: reference note on Lag-Llama, part of the general-purpose TSFM family, distinguished by adapting the LLaMA decoder-only architecture for probabilistic forecasting. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 2 into its own file. Survives Final-implementation limitation #1 (not a text-generation LLM despite the name); size unconfirmed for limitation #2.
---

# Lag-Llama — LLaMA-Architecture Probabilistic Time-Series Model

## Title / what it is

One of the general-purpose Time Series Foundation Models (TSFMs). Its
distinguishing feature: it **adapts the LLaMA decoder-only architecture**
for probabilistic time-series forecasting — reusing a well-known
text-LLM architecture's design, but trained and used entirely on numeric
time-series data, not text.

## Explanation — how it works

Applies lagged values of the time series as input features into a
LLaMA-style decoder-only transformer, trained to output a probabilistic
(distributional, not just point) forecast — useful if uncertainty
quantification matters more than a single-point prediction.

## Input

Lagged historical values of the series — a window of past observations,
not a single point.

## Output format

Explicitly probabilistic — a full predictive distribution over future
values (not just a point estimate), which is the model's specific
selling point.

## Impact — what can be extracted

Same general TSFM caveat: likely underperforms specialized financial
models on K-line data specifically. The probabilistic-output property is
the notable differentiator — could matter if downstream consumers
(`ml_model_pipeline`, risk-sizing logic) want a distribution rather than
a point estimate.

## Is it LLM-dependent?

No — despite reusing the LLaMA *architecture*, this is trained and run
entirely on numeric time-series data, not a text-generation LLM call.
Worth double-checking this framing holds if evaluated for
Final-implementation limitation #1, since the architecture lineage could
cause confusion.

## Model size / base model

**Not confirmed** in this research pass — LLaMA-architecture models can
range widely in parameter count depending on which LLaMA size was
adapted; would need a dedicated lookup before checking against the 2-3GB
cap (limitation #2). Given the "Lag-Llama" project is typically a much
smaller purpose-built model (not a full 7B+ LLaMA), it likely fits, but
this is unconfirmed.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Candidate if probabilistic (distributional) forecasts become useful
downstream — otherwise lower priority than Kronos/Chronos/TimesFM given
the size uncertainty.

## Source

- Foundation Models for Time Series survey (`arXiv:2504.04011`) — the
  LLaMA-architecture detail was found in a follow-up "financial time
  series foundation model 2026" search, not independently deep-dived
