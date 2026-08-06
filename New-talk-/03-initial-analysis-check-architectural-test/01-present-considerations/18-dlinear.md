---
name: dlinear
status: candidate-not-implemented
purpose: reference note on DLinear, a trained-from-scratch price architecture. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 3 into its own file. Survives both Final-implementation limitations (no LLM, small linear model).
---

# DLinear — Simple Linear Mean-Reversion Model

## Title / what it is

One of six trained-from-scratch architectures the source survey found
"actually win on finance" (as opposed to the general-purpose TSFMs, which
tend to underperform). DLinear is the simplest of the six — a linear
model, not a transformer.

## Explanation — how it works

A decomposition-based linear model: splits the series into trend and
seasonal components, applies a simple linear layer to each, and combines
them. No attention mechanism, no nonlinear layers.

## Input

A fixed-length historical lookback window of the price series for a
single ticker, decomposed into trend + seasonal components.

## Output format

A point forecast (a single predicted value or short vector of predicted
returns/prices) — the linear layer's direct output, then thresholded to a
direction for the reported ~50% directional-accuracy figure.

## Impact — what can be extracted

**Directional accuracy: ~50%** (reported). **Strength: mean-reversion,
simple linear** — its value is as a cheap, fast, highly interpretable
baseline rather than a top performer; useful for sanity-checking more
complex models rather than as the primary angle.

## Is it LLM-dependent?

No — a small linear model, not a transformer or LLM.

## Model size / base model

Not stated in the source survey, but linear decomposition models of this
type are typically tiny (well under 1M parameters) — trivially fits under
the 2-3GB cap.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Candidate as a fast, interpretable baseline inside `ml_model_pipeline`,
to sanity-check the more complex models (`21-itransformer.md`,
`22-tft.md`, `23-lpatchtst.md`) against.

## Source

- Reported in `02-price-analysis-methods/price-analysis-methods.md`
  section 3's comparison table; original source not independently
  re-verified in this extraction pass.
