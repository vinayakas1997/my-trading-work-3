---
name: tips-regime-aware-transformer
status: candidate-not-implemented
purpose: reference note on TIPS, a regime-aware transformer architecture. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 5 into its own file. Survives both Final-implementation limitations (no LLM).
---

# TIPS — Transformer with Inductive Prior Synthesis (Regime-Aware)

## Title / what it is

A regime-aware transformer that adapts its temporal inductive biases to
changing market regimes (momentum vs. mean-reversion), rather than using
one fixed architecture across all market conditions.

## Explanation — how it works

Synthesizes an inductive prior tuned to the current detected regime —
i.e., the model's internal assumptions about what kind of temporal
pattern to expect shift depending on whether the market is currently
trending (momentum) or reverting (mean-reversion).

## Input

A historical window of price data, from which the model internally
infers/conditions on the current regime — not a separately-supplied
regime label.

## Output format

A price/return forecast conditioned on an internally-detected regime
state — likely also exposes the detected regime label (momentum vs.
mean-reversion) as an auxiliary output, though this wasn't independently
confirmed in the source.

## Impact — what can be extracted

**Notable finding from the source doc**: no single architecture dominates
all markets; **lightweight LSTM/GRU/Mamba often beat huge transformers on
financial data**. The performance gap comes from *structural constraints*
(which temporal dependencies are emphasized), not model capacity — a
directly relevant finding when comparing `19-lstm.md`,
`31-finmamba-graph-state-space.md` against the larger transformer options
in this folder.

## Is it LLM-dependent?

No — a transformer architecture trained on numeric price data, not an LLM.

## Model size / base model

Not stated in the source survey; would need to read the cited paper
directly before checking against the 2-3GB cap (limitation #2).

## Data sources needed

Price/K-line data only, with regime-detection as an internal or upstream
step. No text — though see `32-news-embedding-regime-detection.md` for a
news-derived regime-detection candidate that could feed this kind of
model as an alternative to price-derived regime detection.

## Fit with existing project structure

Feeds the existing `regime_analysis` angle — the source doc's own "how
this maps to vinu angles" section specifically names regime-aware models
for this role.

## Source

- `arXiv:2603.16985`
