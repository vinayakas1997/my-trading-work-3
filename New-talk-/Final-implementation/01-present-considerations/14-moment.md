---
name: moment
status: candidate-not-implemented
purpose: reference note on MOMENT, part of the general-purpose TSFM family. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 2 into its own file. Survives Final-implementation limitation #1 (not an LLM); size unconfirmed for limitation #2.
---

# MOMENT — General-Purpose Time-Series Foundation Model

## Title / what it is

One of the general-purpose Time Series Foundation Models (TSFMs) named
alongside Chronos, TimesFM, TimeGPT, MOIRAI, Timer/Timer-XL, Lag-Llama, and
PatchFormer in the source survey.

## Explanation — how it works

Not detailed beyond being grouped with the other TSFMs in the original
research pass — a pretrained transformer over generic time series. This
file is thin; a dedicated lookup would be needed before relying on it for
an implementation decision.

## Input

A historical window of one time series — the exact window length and
whether multiple series can be batched together wasn't confirmed in this
research pass.

## Output format

Not confirmed which task mode would be used here — MOMENT is a multi-task
foundation model (forecasting, embeddings, anomaly detection, and
imputation are all typical uses for this model family), so the concrete
output shape depends on which task is selected; not pinned down in this
research pass.

## Impact — what can be extracted

Same general TSFM caveat: likely underperforms specialized financial
models on K-line data specifically, per the source doc's key finding for
the family as a whole.

## Is it LLM-dependent?

No — a time-series forecasting model, not a text-generation LLM.

## Model size / base model

**Not confirmed** in this research pass — would need a dedicated lookup
before checking against the 2-3GB cap (limitation #2).

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Lowest-priority member of the TSFM family for this project given the lack
of detail captured — `09-kronos.md`, `10-chronos.md`, and `11-timesfm.md`
have more established detail and would be the first comparison points.

## Source

- Foundation Models for Time Series survey (`arXiv:2504.04011`) — named
  only, not individually detailed in the original research pass
