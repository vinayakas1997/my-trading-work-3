---
name: chronos
status: candidate-not-implemented
purpose: reference note on Chronos, Amazon's general-purpose time-series foundation model, part of the TSFM family. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 2 into its own file. Survives both Final-implementation limitations (no LLM, all variants under the 2-3GB cap).
---

# Chronos — Amazon's General-Purpose Time-Series Foundation Model

## Title / what it is

One of the general-purpose Time Series Foundation Models (TSFMs) — a
pretrained transformer over generic time series, not specifically trained
on financial K-lines the way Kronos is.

## Explanation — how it works

Converts continuous values into discrete tokens via uniform binning, then
applies a T5-style transformer pretrained across many time-series domains
(not finance-specific).

## Input

A historical window of one time series at a time (length depends on
config, typically hundreds of points) — single-series input per call.

## Output format

A probabilistic forecast — quantile predictions (e.g. P10/P50/P90) over
future time steps, not a single point value.

## Impact — what can be extracted

**Key finding from the source doc**: general TSFMs like Chronos often
**underperform specialized financial models** (e.g. iTransformer, Kronos)
on K-line data specifically — that's precisely why Kronos exists as a
finance-specific alternative. Still useful as a zero-shot baseline or for
cross-checking Kronos/FinCast results.

## Is it LLM-dependent?

No — a time-series foundation model, not a text-generation LLM.

## Model size / base model

**Chronos-T5 ships in small/base/large variants** — per the FinCast paper's
baseline comparison (`30-fincast-foundation-model.md`'s source): small ≈ 8M
params, base ≈ 200M params, large ≈ 710M params. All comfortably fit under
the 2-3GB footprint cap even at fp32.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Candidate zero-shot baseline alongside Kronos for a `kronos_forecast`-style
angle — per the source doc's own finding, expect it to underperform Kronos
specifically on financial data, so treat as a comparison point, not a
first choice.

## Source

- Foundation Models for Time Series survey (`arXiv:2504.04011`)
- Chronos-T5 size detail cross-referenced from the FinCast paper
  (`arXiv:2508.19609`), which uses Chronos-T5 as a baseline
