---
name: kalman-filters
status: candidate-not-implemented
purpose: reference note on Kalman filters, a classical statistical baseline. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 6 into its own file. Survives both Final-implementation limitations trivially (no LLM, no pre-trained model at all).
---

# Kalman Filters — Classical State-Estimation Baseline

## Title / what it is

A classical recursive state-estimation method, one of the baselines the
source survey notes Kronos is benchmarked against.

## Explanation — how it works

Recursively estimates a hidden state (e.g. the "true" underlying price
level or trend) from noisy observations, updating the estimate at each
new data point using a predict-then-correct cycle — a statistical
filtering method, not a neural network.

## Input

The historical price series, processed **sequentially/online** — one new
observation at a time, recursively updating the state estimate, rather
than a big batch window all at once.

## Output format

A filtered/smoothed state estimate (e.g. an underlying trend or "true"
price level) plus its uncertainty (state covariance) — an estimate of
the present/recent state, not necessarily a forward forecast.

## Impact — what can be extracted

A transparent, low-cost baseline for trend/level estimation under noise.
Not competitive with neural/transformer options on the field's own
benchmarks, but useful where interpretability and minimal compute matter
more than peak accuracy.

## Is it LLM-dependent?

No — a classical statistical filtering method, no learned/pretrained
weights.

## Model size / base model

Not applicable — a small number of state-space parameters, effectively
zero footprint.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Baseline/sanity-check option, lowest priority of the four classical
methods here given ARIMA and GARCH have more specific, better-established
roles (general forecasting and volatility respectively).

## Source

- Referenced in `02-price-analysis-methods/price-analysis-methods.md`
  section 6 as one of the classical baselines Kronos is benchmarked
  against; not independently re-sourced in this extraction pass (Kalman
  filtering is a standard, well-documented statistical method).
