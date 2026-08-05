---
name: lpatchtst
status: candidate-not-implemented
purpose: reference note on LPatchTST (LSTM+PatchTST), the best-performing trained-from-scratch price architecture in the source survey. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 3 into its own file. Survives both Final-implementation limitations (no LLM, moderate hybrid model size).
---

# LPatchTST — LSTM + PatchTST Hybrid (Best Downside Robustness)

## Title / what it is

One of six trained-from-scratch architectures the source survey found
"actually win on finance," and the **highest-scoring of the six** on both
directional accuracy and risk-adjusted returns. A hybrid combining LSTM's
sequential processing with PatchTST's patch-based channel-independent
attention.

## Explanation — how it works

Combines the two architectures: LSTM layers capture sequential
dependencies, PatchTST-style patching and channel-independent attention
add the regularization benefit noted in `20-patchtst.md`'s entry — the
hybrid is reported to inherit the strengths of both.

## Input

A historical window of the price series for a single ticker — processed
both sequentially (LSTM) and as patches (PatchTST).

## Output format

A point forecast (hybrid of LSTM and PatchTST's outputs), thresholded to
direction for the reported ~54% figure and to the Sharpe 2.31–2.32
result.

## Impact — what can be extracted

**Directional accuracy: ~54%** (reported, best of the six). **Strength:
best downside robustness, Sharpe 2.31–2.32** — this is the standout result
in the source doc's comparison table, both on raw accuracy and on
risk-adjusted return (Sharpe), which the source doc explicitly flags as
the more meaningful metric ("better statistical forecast ≠ better
returns").

## Is it LLM-dependent?

No — a trained neural hybrid architecture, not an LLM.

## Model size / base model

Not stated in the source survey; as a hybrid of two already-moderate
architectures (LSTM + PatchTST), likely still fits comfortably under the
2-3GB cap, though not independently confirmed here.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

**Top candidate** (with `22-tft.md`) to enhance `ml_model_pipeline` —
the source doc's own "how this maps to vinu angles" section specifically
names TFT/LPatchTST for this role, and this is the stronger performer of
the two by the reported numbers.

## Source

- Reported in `02-price-analysis-methods/price-analysis-methods.md`
  section 3's comparison table; original source not independently
  re-verified in this extraction pass.
