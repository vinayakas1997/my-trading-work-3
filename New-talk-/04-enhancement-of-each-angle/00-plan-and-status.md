---
name: angle-enhancement-plan-and-status
status: not-started
purpose: index and status tracker for the angle-by-angle discussion/enhancement work. One file per angle in this same folder holds that angle's actual discussion/proposal; this file only tracks the list and status.
---

# Angle Enhancement — Plan & Status

## How this folder works

- One `.md` file per angle, named `{NN}-{angle-name}.md` (e.g.
  `01-arima.md`), numbered in the same order the angle directories
  appear under
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/`
  (alphabetical — that's just how the folder is arranged, not a
  priority order).
- Each angle file holds that angle's actual discussion: what it does
  today (verified against real code, not assumed), what's weak or
  worth enhancing, and whatever proposal we land on.
- This file (`00-plan-and-status.md`) is only the index — the table
  below is the single place to check what's discussed and what isn't.
  Don't duplicate per-angle content here; link to the angle's own file.
- Source of truth for the angle list itself is the `angles/` directory
  above, not this table — if an angle is ever added/removed there,
  this table needs a matching update.

## Standard section template (use for every angle file)

Every per-angle `.md` file should follow this same 7-section structure —
decided while writing [01-arima.md](01-arima.md), reused as-is for
consistency so any angle file reads the same way:

1. **Status** — discussed date, status (not-discussed / decided / built),
   reference implementation path verified, links to shared/common pieces
   used (e.g. [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md))
2. **One-line definition** — plain-English, 1-2 sentences, no jargon,
   understandable by anyone
3. **Decided parameters** — table of every parameter/value actually
   agreed on for this angle (thresholds, windows, methods chosen, date
   range, data source, etc.)
4. **Example** — one concrete example of what the output/result actually
   looks like, end to end (raw → tagged → aggregated, if applicable)
5. **Storage, querying, API shape** — how results get stored, how they're
   queried, what the access pattern looks like — written so it's easy to
   actually build from later
6. **What we will achieve / how to use it** — the point of doing this:
   what decisions this data should inform, why it matters
7. **Deeper rationale** — the "show your work" section: why each
   parameter was chosen, what alternatives were rejected and why, source/
   references where applicable, and any open/unresolved caveats (flagged
   honestly, not glossed over)

Don't skip a section — if something genuinely isn't decided yet, write
"not yet decided" in that section rather than omitting it, so it's obvious
what's still open.

## Status table

| # | Angle | File | Status | Notes |
|---|-------|------|--------|-------|
| 01 | `arima` | [01-arima.md](01-arima.md) | decided | design decided, not yet built; reference impl for shared time-slicing tagging, see [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md) |
| 02 | `backtesting_44_metrics` | [02-backtesting_44_metrics.md](02-backtesting_44_metrics.md) | decided | design decided, not yet built; real code computes 18 metrics not 44+, reuses ARIMA's shared time-slicing tagging |
| 03 | `chronos` | [03-chronos.md](03-chronos.md) | decided | design decided, not yet built; genuinely pretrained (upgraded to chronos-t5-large, 710M params), reuses ARIMA's shared time-slicing tagging |
| 04 | `cross_attention_gcn_news_price_fusion` | [04-cross_attention_gcn_news_price_fusion.md](04-cross_attention_gcn_news_price_fusion.md) | decided | not backtestable as-is (untrained, GCN degenerate to 1-node self-loop); real research match found (arXiv 2603.19286); training deferred to future work |
| 05 | `dlinear` | [05-dlinear.md](05-dlinear.md) | decided | design decided, not yet built; genuinely trained-from-scratch each run, every walk-forward step's weights stored, reuses ARIMA's shared time-slicing tagging |
| 06 | `drawdown_deep_dive` | [06-drawdown_deep_dive.md](06-drawdown_deep_dive.md) | decided | design decided, not yet built; adds missing recovery/duration/shape fields, honest news counts instead of unvalidated attribution %, reuses shared time-slicing tagging |
| 07 | `exponential_smoothing` | [07-exponential_smoothing.md](07-exponential_smoothing.md) | decided | design decided, not yet built; Holt's linear trend method, directional-accuracy hit definition, reuses ARIMA's shared design (N=100, flexible refit cadence, tagging) |
| 08 | `garch` | [08-garch.md](08-garch.md) | decided | design decided, not yet built; volatility forecaster (not price), evaluated via QLIKE + directional accuracy, uses vinu-tools' shared garch_volatility function |
| 09 | `itransformer` | [09-itransformer.md](09-itransformer.md) | decided | design decided, not yet built; genuinely trained-from-scratch each run like DLinear; channel-as-token workaround (not true cross-asset attention, same multi-ticker blocker as angle 04's GCN); all 5 channel forecasts stored, weights_ref per step |
| 10 | `kalman_filters` | [10-kalman_filters.md](10-kalman_filters.md) | decided | design decided, not yet built; not a forecaster (state estimator) — filtered_trend sign repurposed as directional signal like DLinear; smoothed state kept whole-history-only to avoid look-ahead bias |
| 11 | `kronos` | [11-kronos.md](11-kronos.md) | decided | design decided, not yet built; genuinely pretrained (Kronos-base, 102M params), full OHLC per horizon step, directional-accuracy hit definition (no band exposed), fallback proxy out of scope |
| 12 | `lag_llama` | [12-lag_llama.md](12-lag_llama.md) | not-discussed | fallback_proxy — real path to pretrained, see `../03-actual-plan-findings/06-models-download.md` |
| 13 | `lpatchtst` | [13-lpatchtst.md](13-lpatchtst.md) | not-discussed | |
| 14 | `lstm` | [14-lstm.md](14-lstm.md) | not-discussed | |
| 15 | `ml_model_pipeline` | [15-ml_model_pipeline.md](15-ml_model_pipeline.md) | not-discussed | **deprecated — superseded**, still present/runnable |
| 16 | `moirai` | [16-moirai.md](16-moirai.md) | not-discussed | fallback_proxy — real path to pretrained |
| 17 | `moment` | [17-moment.md](17-moment.md) | not-discussed | fallback_proxy — real path to pretrained |
| 18 | `news_first_analysis` | [18-news_first_analysis.md](18-news_first_analysis.md) | not-discussed | **deprecated — superseded**, still present/runnable |
| 19 | `news_price_causality` | [19-news_price_causality.md](19-news_price_causality.md) | not-discussed | |
| 20 | `patchtst` | [20-patchtst.md](20-patchtst.md) | not-discussed | |
| 21 | `peer_relative_strength` | [21-peer_relative_strength.md](21-peer_relative_strength.md) | not-discussed | |
| 22 | `pnl_attribution` | [22-pnl_attribution.md](22-pnl_attribution.md) | not-discussed | |
| 23 | `regime_analysis` | [23-regime_analysis.md](23-regime_analysis.md) | not-discussed | |
| 24 | `shock_clustering` | [24-shock_clustering.md](24-shock_clustering.md) | not-discussed | |
| 25 | `shock_personality` | [25-shock_personality.md](25-shock_personality.md) | not-discussed | |
| 26 | `tft` | [26-tft.md](26-tft.md) | not-discussed | |
| 27 | `timer_timerxl` | [27-timer_timerxl.md](27-timer_timerxl.md) | not-discussed | fallback_proxy — real path to pretrained |
| 28 | `timesfm` | [28-timesfm.md](28-timesfm.md) | not-discussed | pretrained foundation model |
| 29 | `tips_regime_aware_transformer` | [29-tips_regime_aware_transformer.md](29-tips_regime_aware_transformer.md) | not-discussed | |
| 30 | `trend_lifecycle` | [30-trend_lifecycle.md](30-trend_lifecycle.md) | not-discussed | |
| 31 | `trend_session_structure` | [31-trend_session_structure.md](31-trend_session_structure.md) | not-discussed | |

**31 angles total** (2 deprecated, still tracked; 29 active). Matches
the real `angles/` directory count after the 4-angle removal — see
`../03-actual-plan-findings/06-models-download.md`.
