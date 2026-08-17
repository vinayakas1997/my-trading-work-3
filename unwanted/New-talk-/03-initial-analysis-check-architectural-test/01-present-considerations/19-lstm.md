---
name: lstm
status: candidate-not-implemented
purpose: reference note on LSTM, a trained-from-scratch price architecture. Extracted from 02-price-analysis-methods/price-analysis-methods.md section 3 into its own file. Survives both Final-implementation limitations (no LLM, small recurrent model).
---

# LSTM — Sequential Nonlinearity Baseline

## Title / what it is

One of six trained-from-scratch architectures the source survey found
"actually win on finance." LSTM (Long Short-Term Memory) is the classical
recurrent-network baseline, predating the transformer-based options in
this comparison.

## Explanation — how it works

A recurrent neural network with gated memory cells, processing the price
sequence one step at a time and carrying forward a learned hidden state —
captures sequential/nonlinear dependencies without attention.

## Input

A sequence of historical time steps for a single ticker, processed one
step at a time by the recurrent network — a window, not a single point.

## Output format

A point forecast (predicted next-step price/return), thresholded to a
direction for the reported ~51% directional-accuracy figure — not
natively a classification output.

## Impact — what can be extracted

**Directional accuracy: ~51%** (reported, the second-best of the six
after LPatchTST/TFT). **Strength: sequential nonlinearity** — a solid,
well-understood baseline; notably, the source doc's TIPS note
(`24-tips-regime-aware-transformer.md`) separately observes "lightweight
LSTM/GRU/Mamba often beat huge transformers on financial data," so this
shouldn't be dismissed as merely a baseline.

## Is it LLM-dependent?

No — a recurrent neural network, not a transformer or LLM.

## Model size / base model

Not stated in the source survey; LSTMs for this kind of task are typically
small (well under 50M parameters depending on hidden size/layers) —
comfortably fits under the 2-3GB cap.

## Data sources needed

Price/K-line data only. No text.

## Fit with existing project structure

Candidate regressor inside `ml_model_pipeline` — worth taking seriously
given the "lightweight models often beat huge transformers" finding
elsewhere in the same source doc, not just as a baseline to beat.

## Source

- Reported in `02-price-analysis-methods/price-analysis-methods.md`
  section 3's comparison table; original source not independently
  re-verified in this extraction pass.
