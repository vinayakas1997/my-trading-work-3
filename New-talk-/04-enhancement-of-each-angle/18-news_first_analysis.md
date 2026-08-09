---
name: angle-18-news_first_analysis
status: decided
purpose: discussion for the `news_first_analysis` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/news_first_analysis/`.
---

# 18 — news_first_analysis

**Title (from spec.yaml):** News First Analysis

## 1) Status

- Discussed: 2026-08-07
- Status: decided — **confirmed redundant, not required. No enhancement
  proposed.** Same category as `ml_model_pipeline` (angle 15), not a
  design discussion like the forecasting angles.
- Reference implementation verified against real code: `compute.py` /
  `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/news_first_analysis/`
- The code's own module docstring says it plainly: **"DEPRECATED, not
  deleted"** — its ground (categorization, sentiment, event/priority
  scoring) is now covered by `vinu-news`'s own Section-1 methods
  (`vinu-news/vinu_news/analysis/methods/` —
  `event_type_classification`, `vader_finance_tuned_sentiment`, plus
  vinu-news's pre-existing FinBERT/NER/category pipeline), which is
  where the project's reconciliation doc recommends this kind of news
  analysis live going forward, not duplicated here a third time. Kept in
  the codebase, not removed, only because deleting a working feature was
  judged out of scope for the pass that made this call.
- No shared/common piece — out of scope, this angle isn't getting the
  standard tagging/storage/backtest treatment.

## 2) One-line definition

A news-analysis angle that categorizes articles, scores sentiment, and
computes session-level baselines/priority for a symbol — not required,
because `vinu-news` (a separate, dedicated component) already does this
same job as its actual primary purpose, and is the recommended place for
this kind of work going forward.

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
here**, not a build plan. `vinu-news`'s Section-1 methods already cover
the same ground, in the component actually meant to own news analysis.

## 7) Deeper rationale

**Why redundant, not just old:** this angle's job (categorize news,
score sentiment, compute priority) is duplicated — a third time, per the
code's own docstring — by work that already lives in `vinu-news`, a
separate component dedicated to news analysis. Having the same logic
maintained in two places (`vinu-initial-analysis`'s angle system and
`vinu-news`'s own pipeline) is duplication with no upside, not a case of
two genuinely different approaches worth comparing.

**Why not delete it now:** same reasoning as `ml_model_pipeline` —
removing a working, tested feature is a bigger, separate decision than
this angle-by-angle discussion pass is scoped to make. Left as-is; actual
removal is a follow-up decision for whoever owns that call.

**Open/unresolved:** none — this is a closed call, not an open design
question, same status as `ml_model_pipeline`.
