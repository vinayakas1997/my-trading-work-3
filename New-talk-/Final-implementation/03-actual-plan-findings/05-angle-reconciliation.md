---
name: angle-reconciliation
status: discussion-phase
purpose: classifies the 12 real angles already implemented in vinu-initial-analysis (found in 04-build-status.md) against the 32 planned methods — keep / redundant-remove / upgrade-candidate — per the decision rule "if good keep it, if redundant remove it, if the new method is a better/more advanced version, upgrade."
---

# Angle Reconciliation — Existing 12 Angles vs. the 32-Method Plan

## Keep (unique, no overlap with the 32-list) — 7

| Angle | Why it stays |
|---|---|
| `backtesting_44_metrics` | Portfolio/performance metrics (Sharpe, Sortino, MaxDD, VaR, CVaR, etc.) — nothing in the 32-list covers this ground. |
| `drawdown_deep_dive` | Drawdown detection + news attribution blend — no planned equivalent. |
| `news_price_causality` | Granger causality, Pearson correlation, event study, significance model — already rigorously implemented (L3 methodology). Nothing in the 32-list replaces or improves on this. Don't touch. |
| `peer_relative_strength` | No planned equivalent. |
| `shock_clustering` | Dynamic covariance clustering — no planned equivalent. |
| `trend_lifecycle` | Peak/trough pattern library + KNN similarity + stage classification — no planned equivalent, already fairly advanced. |
| `trend_session_structure` | Session-level `trend_lifecycle` variant — same reasoning. |

## Redundant — 1

| Angle | Why it's redundant | Recommendation |
|---|---|---|
| `news_first_analysis` | Overlaps two ways: with planned methods `01-event-type-classification`, `03-velocity-spike-anomaly-detection`, `06-vader-finance-tuned-sentiment` from the 32-list, **and** with vinu-news's own already-working NER/FinBERT-sentiment/event-classification pipeline (see `04-build-status.md`). Three implementations of roughly the same news-analysis work spread across two components. | Consolidate into vinu-news's existing pipeline; drop this angle rather than building the 32-list's news methods a third time. |

## Upgrade candidates — 2

| Angle | What it does now | What's more advanced | Recommendation |
|---|---|---|---|
| `ml_model_pipeline` | Trains/evaluates 9 generic tabular ML models for price prediction (OOS IC, auto-selection). | Planned methods `09`-`24` (kronos, chronos, timesfm, timegpt, moirai, moment, timer-timerxl, lag-llama, patchformer, dlinear, lstm, patchtst, itransformer, tft, lpatchtst, tips) — purpose-built sequence/foundation-model architectures for time series, a real architectural upgrade over generic tabular ML for this exact job. | Replace, don't run both. |
| `regime_analysis` | Rule-based 4-regime classifier + transition matrix on price/stats. | `24-tips-regime-aware-transformer` and `32-news-embedding-regime-detection` — not strict replacements (different inputs/approach: one's a forecasting model, one's news-driven), but more advanced regime signals. | Not a clean replacement — keep `regime_analysis` running, compare against 24/32 once those are built, decide later. |

## Keep + extract — 1

| Angle | Situation | Recommendation |
|---|---|---|
| `shock_personality` | Has real GARCH (`vinu_tools.compute.risk.volatility.garch_volatility`) embedded internally for its own volatility-characterization purpose. | Keep `shock_personality` as-is. Additionally expose a thin standalone `26-garch` angle that calls the same underlying `vinu_tools` function, so GARCH also exists in the plan's per-method storage/API shape — without duplicating the math. |

## Different stage — not part of this decision — 1

| Angle | Why it's excluded from keep/remove/upgrade |
|---|---|
| `pnl_attribution` | Push-fed from vinu-live's closed positions — this is stage-2/3 territory (during/after trading), not stage-1 pre-analysis where the 32-method plan lives. Leave untouched; out of scope entirely. |

## Net effect on the 32-method build

- `26-garch` gets a head start (extract from `shock_personality`'s existing call).
- `09`-`24` (the sequence/foundation-model family) supersede `ml_model_pipeline` — building them retires that angle rather than adding alongside it.
- `01`, `03`, `06` (and the rest of the Section-1 news methods) should be built/reused via vinu-news, not vinu-initial-analysis — reinforces the component-boundary question already raised in `04-build-status.md`.
- The other 21 planned methods (kronos-family minus what's covered above, plus 27-31) have no existing code to reconcile against — straightforward new builds.

## Related files

- `04-build-status.md` — where the 12 real angles and their code locations were found
- `01-method-separation.md` / `../01-present-considerations/00-index.md` — the 32-method list this reconciles against
