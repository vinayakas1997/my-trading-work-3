---
name: timesfm
status: candidate-not-implemented
purpose: reference note on TimesFM, Google's general-purpose time-series foundation model, part of the TSFM family. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 2 into its own file. Survives both Final-implementation limitations (no LLM, both variants under the 2-3GB cap).
---

# TimesFM — Google's General-Purpose Time-Series Foundation Model

## Title / what it is

One of the general-purpose Time Series Foundation Models (TSFMs) — Google's
pretrained transformer for generic time-series forecasting.

## Explanation — how it works

A decoder-only transformer pretrained on a large, diverse corpus of
time-series data (not finance-specific), used zero-shot or fine-tuned for
a target series.

## Input

A historical window/context of one time series at a time — same general
single-series input pattern as Chronos.

## Output format

A point forecast (and, depending on configuration, prediction intervals)
for future time-series values — standard TSFM-style output.

## Impact — what can be extracted

Same caveat as the rest of the TSFM family (`10-chronos.md`): general TSFMs
including TimesFM often **underperform specialized financial models** on
K-line data specifically. Useful as a zero-shot baseline / comparison point
against Kronos and FinCast, not necessarily as a first-choice model.

## Is it LLM-dependent?

No — a time-series foundation model, not a text-generation LLM.

## Model size / base model

**Ships in 200M and 500M parameter variants** — per the FinCast paper's
baseline comparison (`30-fincast-foundation-model.md`'s source). Both fit
comfortably under the 2-3GB footprint cap (≈0.4GB and ≈1.0GB at fp16
respectively).

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Candidate zero-shot baseline alongside Kronos/Chronos for a
`kronos_forecast`-style angle.

## Source

- Foundation Models for Time Series survey (`arXiv:2504.04011`)
- TimesFM size detail cross-referenced from the FinCast paper
  (`arXiv:2508.19609`), which uses TimesFM as a baseline
