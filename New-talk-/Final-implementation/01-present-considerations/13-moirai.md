---
name: moirai
status: candidate-not-implemented
purpose: reference note on MOIRAI, part of the general-purpose TSFM family, distinguished by its any-variate attention mechanism. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 2 into its own file. Survives Final-implementation limitation #1 (not an LLM); size unconfirmed for limitation #2.
---

# MOIRAI — Any-Variate Time-Series Foundation Model

## Title / what it is

One of the general-purpose Time Series Foundation Models (TSFMs). Its
distinguishing feature: it handles an **arbitrary number of input series**
through an "any-variate" attention mechanism — relevant if a future angle
wants to feed many tickers' K-lines into one model call rather than one
model per ticker.

## Explanation — how it works

The "any-variate" attention mechanism lets the model accept a variable
number of input time-series channels at inference time, rather than being
fixed to a specific number of variates the way many forecasting models are
— potentially useful for a multi-ticker version of a price-only angle
without retraining per ticker-count.

## Input

A historical window across **potentially multiple series/tickers at
once** — the any-variate mechanism is specifically what lets the input
be a set of tickers' windows fed jointly, not just one.

## Output format

A multivariate probabilistic forecast across however many input series
are fed in via its any-variate mechanism.

## Impact — what can be extracted

Same general TSFM caveat: likely underperforms specialized financial
models on K-line data specifically. The any-variate property is the
notable differentiator worth remembering if a cross-ticker price angle
gets built later (relevant to `peer_relative_strength`).

## Is it LLM-dependent?

No — a time-series foundation model, not a text-generation LLM.

## Model size / base model

**Not confirmed** in this research pass — would need a dedicated lookup
before checking against the 2-3GB cap (limitation #2). MOIRAI is published
by Salesforce with multiple size variants (small/base/large is the general
pattern in this model family); exact figures not verified here.

## Data sources needed

Price/K-line data only, potentially multiple tickers simultaneously (the
any-variate property). No text.

## Fit with existing project structure

Candidate for a multi-ticker price-only angle, or an extension of
`peer_relative_strength`, given the any-variate design — more relevant to
cross-stock use than the other single-series TSFMs in this family.

## Source

- Foundation Models for Time Series survey (`arXiv:2504.04011`) — the
  any-variate attention detail was found in a follow-up "financial time
  series foundation model 2026" search, not independently deep-dived
