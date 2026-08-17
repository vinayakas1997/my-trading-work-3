---
name: timegpt
status: candidate-not-implemented
purpose: reference note on TimeGPT, part of the general-purpose TSFM family. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 2 into its own file. Survives Final-implementation limitation #1 (not an LLM); size unconfirmed for limitation #2.
---

# TimeGPT — General-Purpose Time-Series Foundation Model

## Title / what it is

One of the general-purpose Time Series Foundation Models (TSFMs) named
alongside Chronos, TimesFM, MOIRAI, MOMENT, Timer/Timer-XL, Lag-Llama, and
PatchFormer in the source survey. Despite the "GPT" in the name, this is a
time-series forecasting model, not a text-generation LLM.

## Explanation — how it works

Not detailed beyond being grouped with the other TSFMs: a pretrained
transformer over generic time series, offered commercially via API
(Nixtla). No architecture specifics were captured in the original research
pass — this file is thinner than the others in this family; a dedicated
lookup would be needed to fill in specifics before relying on it.

## Input

A historical window of one time series per API call — same general
single-series pattern as the rest of the TSFM family; not independently
confirmed for this specific model.

## Output format

Typically a point forecast with prediction intervals, per Nixtla's
standard API output shape — not independently confirmed for this specific
model in this research pass.

## Impact — what can be extracted

Same general caveat as the rest of the TSFM family: likely underperforms
specialized financial models (Kronos, iTransformer) on K-line data
specifically, per the source doc's key finding for the TSFM family as a
whole. Not independently verified for TimeGPT specifically.

## Is it LLM-dependent?

No — despite the name, this is a time-series forecasting model, not a
text-generation LLM.

## Model size / base model

**Not confirmed.** TimeGPT is typically offered as a hosted API (Nixtla)
rather than an openly-published parameter count — would need a dedicated
lookup to confirm whether a self-hostable checkpoint exists and its size,
before it could be checked against the 2-3GB cap (limitation #2).

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Candidate zero-shot baseline alongside the rest of the TSFM family, lowest
priority of the group given the unconfirmed self-hosting/size situation.

## Source

- Foundation Models for Time Series survey (`arXiv:2504.04011`) — named
  only, not individually detailed in the original research pass
