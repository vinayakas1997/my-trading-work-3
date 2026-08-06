---
name: garch
status: candidate-not-implemented
purpose: reference note on GARCH, a classical volatility-modeling baseline. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 6 into its own file. Survives both Final-implementation limitations trivially (no LLM, no pre-trained model at all — a fitted statistical model).
---

# GARCH — Classical Volatility Model

## Title / what it is

Generalized AutoRegressive Conditional Heteroskedasticity — the classical
statistical model specifically for **volatility** forecasting, one of the
baselines the source survey notes Kronos is benchmarked against.

## Explanation — how it works

Models the conditional variance of returns as a function of past squared
returns and past variance — captures volatility clustering (calm periods
followed by calm, turbulent followed by turbulent) directly, without a
neural network.

## Input

The historical returns series for a single ticker, used to fit the
conditional-variance model — no fixed window, similar to ARIMA.

## Output format

A forecasted conditional variance (volatility) for the next period — a
single float, not a price/return forecast; this is a volatility model
specifically, not a directional one.

## Impact — what can be extracted

**The source doc singles this out specifically**: "for volatility
specifically, GARCH remains the transparent parametric alternative" —
i.e., even among the classical baselines, this is called out as the one
still worth taking seriously for volatility forecasting specifically,
not just a strawman.

## Is it LLM-dependent?

No — a classical statistical model, no learned/pretrained weights.

## Model size / base model

Not applicable — a small number of fitted coefficients, effectively zero
footprint.

## Data sources needed

Price/K-line data only (returns series). No text.

## Fit with existing project structure

Directly relevant to any volatility-forecasting angle, and as a
transparent comparison point against Kronos's volatility-forecasting
claim (`09-kronos.md`'s "−9% MAE in volatility forecasting" figure was
measured against baselines including this one).

## Source

- Referenced in `02-price-analysis-methods/price-analysis-methods.md`
  section 6 as one of the classical baselines Kronos is benchmarked
  against, specifically called out for volatility; not independently
  re-sourced in this extraction pass (GARCH is a standard, well-documented
  statistical method).
