---
name: exponential-smoothing
status: candidate-not-implemented
purpose: reference note on exponential smoothing, a classical statistical baseline. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 6 into its own file. Survives both Final-implementation limitations trivially (no LLM, no pre-trained model at all).
---

# Exponential Smoothing — Classical Statistical Baseline

## Title / what it is

A classical forecasting method that weights recent observations more
heavily than older ones via an exponentially-decaying weight scheme, one
of the baselines the source survey notes Kronos is benchmarked against.

## Explanation — how it works

Computes a forecast as a weighted average of past observations, with
weights decaying exponentially as they get older — simple variants
(single) handle level only; extended variants (double/triple, e.g. Holt-
Winters) add trend and seasonality components.

## Input

The historical price series for a single ticker — weights recent
observations more than older ones, no fixed lookback window required.

## Output format

A point forecast (a weighted average of past values), optionally
decomposed into level/trend/seasonal components for the Holt-Winters
variant.

## Impact — what can be extracted

A transparent, minimal-compute baseline. Not competitive with
neural/transformer options on the field's own benchmarks, but essentially
free to run and useful as a floor comparison.

## Is it LLM-dependent?

No — a classical statistical method, no learned/pretrained weights.

## Model size / base model

Not applicable — a handful of smoothing-parameter coefficients,
effectively zero footprint.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Baseline/sanity-check option alongside ARIMA, GARCH, and Kalman filters —
lowest-effort of the four to stand up given its simplicity.

## Source

- Referenced in `02-price-analysis-methods/price-analysis-methods.md`
  section 6 as one of the classical baselines Kronos is benchmarked
  against; not independently re-sourced in this extraction pass
  (exponential smoothing is a standard, well-documented statistical
  method).
