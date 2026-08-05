---
name: itransformer
status: candidate-not-implemented
purpose: reference note on iTransformer, a trained-from-scratch price architecture with cross-asset correlation modeling. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 3 into its own file. Survives both Final-implementation limitations (no LLM, moderate transformer size).
---

# iTransformer — Cross-Asset Correlation Transformer

## Title / what it is

One of six trained-from-scratch architectures the source survey found
"actually win on finance." iTransformer inverts the usual transformer
setup: instead of tokenizing time steps, it tokenizes *variates*
(different series/assets), letting attention directly model cross-asset
correlations.

## Explanation — how it works

Each input variate (e.g. a different ticker's price series) becomes a
token; self-attention across these variate-tokens lets the model learn
which assets move together — this is what gives it a cross-asset/macro
sensitivity the single-series models (DLinear, LSTM, PatchTST) don't have.

## Input

A historical window across **multiple variates/tickers fed jointly** —
this is the one model in the trained-from-scratch table that specifically
needs a multi-ticker input to exploit its cross-asset attention.

## Output format

A point forecast per variate/asset, produced jointly across all input
tickers via the attention mechanism — this is what lets it capture
cross-asset correlation in the output itself, not just the input.

## Impact — what can be extracted

**Directional accuracy: ~50%** (reported). **Strength: cross-asset
correlations (macro links)** — its real value isn't raw directional
accuracy but its structural fit with a multi-ticker setup like this
project's AAPL/TSLA/JNJ universe.

## Is it LLM-dependent?

No — a transformer architecture trained on numeric price data, not an LLM.

## Model size / base model

Not stated in the source survey; iTransformer configurations in the
published paper are typically moderate-sized transformers — likely fits
under the 2-3GB cap, though not independently confirmed here.

## Data sources needed

Price/K-line data for multiple tickers simultaneously — this is the one
model in the trained-from-scratch table that specifically needs a
multi-ticker input to exploit its architecture.

## Fit with existing project structure

Directly extends `peer_relative_strength` (cross-stock/cross-index links)
— the source doc's own "how this maps to vinu angles" section flags this
exact connection. Also comparable to `13-moirai.md`'s any-variate design
and `31-finmamba-graph-state-space.md`'s cross-stock graph layer as
alternative approaches to the same cross-asset problem.

## Source

- ICLR 2024
