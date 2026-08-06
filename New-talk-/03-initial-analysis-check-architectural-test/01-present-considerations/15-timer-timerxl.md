---
name: timer-timerxl
status: candidate-not-implemented
purpose: reference note on Timer/Timer-XL, part of the general-purpose TSFM family. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 2 into its own file. Survives Final-implementation limitation #1 (not an LLM); size unconfirmed for limitation #2.
---

# Timer / Timer-XL — General-Purpose Time-Series Foundation Models

## Title / what it is

One of the general-purpose Time Series Foundation Models (TSFMs) named
alongside Chronos, TimesFM, TimeGPT, MOIRAI, MOMENT, Lag-Llama, and
PatchFormer in the source survey. Timer-XL is presumably a larger-context
variant of Timer.

## Explanation — how it works

Not detailed beyond being grouped with the other TSFMs in the original
research pass. This file is thin; a dedicated lookup would be needed
before relying on it for an implementation decision.

## Input

A historical window of one time series, split into patches for
processing — window/patch-based, not a single bar.

## Output format

A point forecast, generated in a next-patch autoregressive style similar
to Kronos's next-token approach — not independently confirmed in detail.

## Impact — what can be extracted

Same general TSFM caveat: likely underperforms specialized financial
models on K-line data specifically.

## Is it LLM-dependent?

No — a time-series forecasting model, not a text-generation LLM.

## Model size / base model

**Not confirmed** in this research pass — would need a dedicated lookup
before checking against the 2-3GB cap (limitation #2).

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Lowest-priority member of the TSFM family for this project given the lack
of detail captured.

## Source

- Foundation Models for Time Series survey (`arXiv:2504.04011`) — named
  only, not individually detailed in the original research pass
