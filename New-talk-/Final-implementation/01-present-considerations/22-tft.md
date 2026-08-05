---
name: tft
status: candidate-not-implemented
purpose: reference note on TFT (Temporal Fusion Transformer), a trained-from-scratch price architecture. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 3 into its own file. Survives both Final-implementation limitations (no LLM, moderate transformer size).
---

# TFT — Temporal Fusion Transformer

## Title / what it is

One of six trained-from-scratch architectures the source survey found
"actually win on finance," and one of the two strongest performers
(alongside LPatchTST) in the comparison table.

## Explanation — how it works

Combines LSTM-style sequence processing with a variable-selection network
that learns to weight which input features matter at each time step,
plus interpretable multi-head attention — the variable-selection step is
what the source doc credits for filtering noise other models don't.

## Input

A historical window of observed values, plus optionally **known-future
inputs** (e.g. an earnings-date calendar) and **static covariates** (e.g.
sector) — a richer input schema than a plain price window, which is what
the variable-selection network operates over.

## Output format

**Natively quantile forecasts** (e.g. P10/P50/P90), a signature feature
of the Temporal Fusion Transformer architecture — richer than a single
point estimate, directly usable for uncertainty-aware sizing decisions.

## Impact — what can be extracted

**Directional accuracy: ~53%** (reported, tied for second-best). The
source doc's takeaway line applies directly here: "better statistical
forecast ≠ better returns — Sharpe-strong models (TFT, LPatchTST) win on
risk-adjusted terms, not RMSE." **Strength: variable-selection filters
noise.**

## Is it LLM-dependent?

No — a transformer architecture trained on numeric price data, not an LLM.

## Model size / base model

Not stated in the source survey; TFT configurations in the literature are
typically moderate-sized (tens of millions of parameters) — likely fits
under the 2-3GB cap, though not independently confirmed here.

## Data sources needed

Price/K-line data, optionally with additional known-future inputs (the
architecture supports static/known/observed input categories, though the
source doc doesn't specify which were used here). No text required.

## Fit with existing project structure

One of the two top candidates (with `23-lpatchtst.md`) to enhance
`ml_model_pipeline` — the source doc's own "how this maps to vinu angles"
section specifically names TFT/LPatchTST for this role (regressors →
temporal fusion).

## Source

- Reported in `02-price-analysis-methods/price-analysis-methods.md`
  section 3's comparison table; original source not independently
  re-verified in this extraction pass.
