---
name: patchformer
status: candidate-not-implemented
purpose: reference note on PatchFormer, part of the general-purpose TSFM family. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 2 into its own file. Survives Final-implementation limitation #1 (not an LLM); size unconfirmed for limitation #2.
---

# PatchFormer — General-Purpose Time-Series Foundation Model

## Title / what it is

One of the general-purpose Time Series Foundation Models (TSFMs) named
alongside Chronos, TimesFM, TimeGPT, MOIRAI, MOMENT, Timer/Timer-XL, and
Lag-Llama in the source survey. Distinct from PatchTST
(`20-patchtst.md`) — a trained-from-scratch architecture in the source
doc's separate comparison table, not part of this TSFM family.

## Explanation — how it works

Not detailed beyond being grouped with the other TSFMs in the original
research pass, and having its own arXiv citation (below) — a dedicated
read of that paper would be needed to fill in the architecture specifics.

## Input

A historical window of one time series, split into patches — same
general pattern as the rest of this family; not confirmed in detail.

## Output format

A forecast (point or probabilistic) — not confirmed in detail without
reading the cited paper directly.

## Impact — what can be extracted

Same general TSFM caveat: likely underperforms specialized financial
models on K-line data specifically, per the source doc's key finding for
the family as a whole.

## Is it LLM-dependent?

No — a time-series forecasting model, not a text-generation LLM.

## Model size / base model

**Not confirmed** in this research pass — would need to read the cited
paper directly before checking against the 2-3GB cap (limitation #2).

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Candidate zero-shot baseline alongside the rest of the TSFM family — has
its own citation (unlike TimeGPT/MOIRAI/MOMENT/Timer above), so slightly
higher priority to actually read if this family gets evaluated.

## Source

- `arXiv:2601.20845`
