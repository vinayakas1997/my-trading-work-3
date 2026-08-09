---
name: angle-15-ml_model_pipeline
status: decided
purpose: discussion for the `ml_model_pipeline` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/ml_model_pipeline/`.
---

# 15 — ml_model_pipeline

**Title (from spec.yaml):** ML Model Pipeline

## 1) Status

- Discussed: 2026-08-07
- Status: decided — **confirmed redundant, no enhancement proposed. Not a
  design discussion like the other angles.**
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/ml_model_pipeline/`
- The code's own module docstring says it plainly: **"DEPRECATED, not
  deleted"** — it names the exact set of angles that supersede it:
  `dlinear, lstm, patchtst, itransformer, tft, lpatchtst,
  tips_regime_aware_transformer, kronos, chronos, timesfm, ...` — which
  is precisely the set of purpose-built forecasting angles being worked
  through one-by-one in this same folder. Kept in the codebase, not
  removed, only because deleting a working feature was judged out of
  scope for the pass that made this call — the docstring says outright
  "removing it outright is a follow-up decision, not done here."
- No shared/common piece — out of scope, this angle isn't getting the
  standard tagging/storage/backtest treatment.

## 2) One-line definition

A generic machine-learning pipeline that trains 9 different off-the-shelf
tabular models (ridge regression, random forest, XGBoost, LightGBM, etc.)
on hand-engineered price features and picks whichever one scores best —
superseded by the purpose-built forecasting models (ARIMA, DLinear, LSTM,
Chronos, Kronos, etc.) now being built one at a time in this folder,
which are architected specifically for price-sequence forecasting instead
of generic tabular regression.

## 3) Decided parameters

Not applicable — no enhancement is being designed for this angle. It
stays as legacy/superseded code, unchanged.

## 4) Example

Not applicable.

## 5) Storage, querying, API shape

Not applicable — this angle isn't being backtested or wired into the
shared tagging/storage infrastructure the other angles use.

## 6) What we will achieve / how to use it

Nothing new — this section documents a **decision not to invest further
here**, not a build plan. The purpose-built angles already cover the same
ground with architectures actually designed for the task.

## 7) Deeper rationale

**Why redundant, not just old:** every purpose-built angle this project
is now designing (ARIMA's statistical baseline, DLinear/LSTM/LPatchTST's
trained-from-scratch neural nets, Chronos/Kronos's pretrained foundation
models) targets the exact same job — forecast the next price/return from
recent price history — with an architecture chosen specifically for
sequential financial data. `ml_model_pipeline` instead throws generic
tabular-ML models at hand-engineered features, a strictly older and less
targeted approach the codebase's own docstring already flags as
superseded.

**Why not delete it now:** that's explicitly called out as a separate,
bigger decision than this discussion pass is scoped to make — removing a
working, tested feature is a different kind of call than deciding not to
enhance it further. Left as-is; a future pass can decide whether to
actually remove it once the purpose-built angles are built and proven
out.

**Open/unresolved:** none — this is a closed call, not an open design
question. If a future need arises for a generic tabular-ML fallback
(e.g. comparing purpose-built architectures against a plain
gradient-boosted-tree baseline on the same features), that would be a
new, deliberate decision — not a revival of this angle as-is.
