---
name: arima
status: candidate-not-implemented
purpose: reference note on ARIMA, a classical statistical baseline. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 6 into its own file. Survives both Final-implementation limitations trivially (no LLM, no pre-trained model at all — a fitted statistical model).
---

# ARIMA — Classical Statistical Baseline

## Title / what it is

AutoRegressive Integrated Moving Average — the classical statistical
time-series forecasting model, one of the baselines the source survey
notes Kronos is benchmarked against.

## Explanation — how it works

Fits an autoregressive + moving-average model to the (differenced, for
stationarity) price series — a parametric statistical model, not a
neural network. No pretraining; fit fresh per series.

## Input

The full historical price/return series up to the current point for a
single ticker — no fixed window; the model is fit (or refit) against
whatever history is chosen.

## Output format

A point forecast plus a confidence interval — ARIMA's standard
statistical output shape.

## Impact — what can be extracted

A transparent, fully-interpretable baseline. Not competitive with the
neural/transformer options on the field's own benchmarks, but useful as
a sanity-check floor and because it requires no training infrastructure
at all — can run standalone.

## Is it LLM-dependent?

No — a classical statistical model, no learned/pretrained weights.

## Model size / base model

Not applicable — ARIMA has no "model size" in the neural-network sense;
it's a small number of fitted coefficients (p, d, q order parameters),
effectively zero footprint.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Baseline/sanity-check for `ml_model_pipeline` and any new price-only
angle — the source doc notes Kronos itself is benchmarked against this
family.

## Source

- Referenced in `02-price-analysis-methods/price-analysis-methods.md`
  section 6 as one of the classical baselines Kronos is benchmarked
  against; not independently re-sourced in this extraction pass (ARIMA
  is a standard, well-documented statistical method).
