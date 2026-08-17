---
name: patchtst
status: candidate-not-implemented
purpose: reference note on PatchTST, a trained-from-scratch price architecture. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 3 into its own file. Survives both Final-implementation limitations (no LLM, moderate transformer size). Distinct from PatchFormer (17-patchformer.md), a TSFM-family model.
---

# PatchTST — Channel-Independent Patch Transformer

## Title / what it is

One of six trained-from-scratch architectures the source survey found
"actually win on finance." PatchTST splits each time series into
patches (like Vision Transformer patches an image) and treats channels
(variates) independently.

## Explanation — how it works

Segments the input series into fixed-length patches, embeds each patch as
a token, and applies standard transformer self-attention across patches —
critically, each variate/channel is processed independently rather than
mixed together, which the source doc notes acts as a regularizer.

## Input

A historical window split into patches, processed **independently per
channel/variate** — multiple tickers can be included but are not mixed
together (that's the "channel independence" property).

## Output format

A point forecast per channel (price series), independently per variate
given the channel-independence design; thresholded to direction for the
~50% figure.

## Impact — what can be extracted

**Directional accuracy: ~50%** (reported). **Strength: channel
independence = regularizer** — the independent-channel design reduces
overfitting risk compared to models that mix channels, at the cost of not
directly modeling cross-channel (cross-asset) correlations the way
iTransformer does.

## Is it LLM-dependent?

No — a transformer architecture trained on numeric price data, not an LLM.

## Model size / base model

Not stated in the source survey; PatchTST configurations in the
literature are typically small-to-moderate transformers (a few million to
tens of millions of parameters) — comfortably fits under the 2-3GB cap.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Candidate regressor inside `ml_model_pipeline`, useful as a
regularization-favoring alternative to `21-itransformer.md` when
overfitting on limited AAPL/TSLA/JNJ history is a concern.

## Source

- Reported in `02-price-analysis-methods/price-analysis-methods.md`
  section 3's comparison table; original source not independently
  re-verified in this extraction pass.
