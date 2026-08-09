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
| 06 | `drawdown_deep_dive` | [06-drawdown_deep_dive.md](06-drawdown_deep_dive.md) | decided | design decided, not yet built; adds missing recovery/duration/shape fields, honest news counts instead of unvalidated attribution %, reuses shared time-slicing tagging; **updated 2026-08-07** — fixed -2% threshold replaced with volatility-adaptive `k × ATR%`, k swept not fixed |
| 07 | `exponential_smoothing` | [07-exponential_smoothing.md](07-exponential_smoothing.md) | decided | design decided, not yet built; Holt's linear trend method, directional-accuracy hit definition, reuses ARIMA's shared design (N=100, flexible refit cadence, tagging) |
| 08 | `garch` | [08-garch.md](08-garch.md) | decided | design decided, not yet built; volatility forecaster (not price), evaluated via QLIKE + directional accuracy, uses vinu-tools' shared garch_volatility function |
| 09 | `itransformer` | [09-itransformer.md](09-itransformer.md) | decided | design decided, not yet built; genuinely trained-from-scratch each run like DLinear; channel-as-token workaround (not true cross-asset attention, same multi-ticker blocker as angle 04's GCN); all 5 channel forecasts stored, weights_ref per step |
| 10 | `kalman_filters` | [10-kalman_filters.md](10-kalman_filters.md) | decided | design decided, not yet built; not a forecaster (state estimator) — filtered_trend sign repurposed as directional signal like DLinear; smoothed state kept whole-history-only to avoid look-ahead bias |
| 11 | `kronos` | [11-kronos.md](11-kronos.md) | decided | design decided, not yet built; genuinely pretrained (Kronos-base, 102M params), full OHLC per horizon step, directional-accuracy hit definition (no band exposed), fallback proxy out of scope |
| 12 | `lag_llama` | [12-lag_llama.md](12-lag_llama.md) | decided | design decided, not yet built; always `fallback_proxy` (AR(5) OLS, genuine 5-quantile Gaussian output vs. real model's Student-t), real weights (2.45M params) already downloaded but wiring deferred by decision over a shared-env dependency conflict, see `../03-initial-analysis-check-architectural-test/03-actual-plan-findings/06-models-download.md`; adds pinball-loss + RMSE/MAE as new metrics |
| 13 | `lpatchtst` | [13-lpatchtst.md](13-lpatchtst.md) | decided | design decided, not yet built; genuinely trained-from-scratch (LSTM + shared `patchtst` patch branch), native 1-step horizon kept as-is; corrected a miscited benchmark (57.7% real hit rate, not the ~54% originally claimed — see arXiv:2603.01820) |
| 14 | `lstm` | [14-lstm.md](14-lstm.md) | decided | design decided, not yet built; genuinely trained-from-scratch, native 1-step horizon; corrected a miscited benchmark (55.4% real hit rate, not the ~51% originally claimed — same source paper as lpatchtst, arXiv:2603.01820) |
| 15 | `ml_model_pipeline` | [15-ml_model_pipeline.md](15-ml_model_pipeline.md) | decided | confirmed redundant (code's own docstring names the superseding angles); no enhancement proposed, left as-is, still present/runnable |
| 16 | `moirai` | [16-moirai.md](16-moirai.md) | decided | design decided, not yet built; always `fallback_proxy` (AR(3), point+p10/p90), real weights downloaded but wiring is **on hold** (not scoped future work like lag_llama) — env dependency conflict plus a structural any-variate/single-symbol interface mismatch that a dependency fix alone wouldn't resolve |
| 17 | `moment` | [17-moment.md](17-moment.md) | decided | design decided, not yet built; always `fallback_proxy` (drift+residual-quantile), real-weights wiring **decided against** (not deferred) — MOMENT's own literature shows forecasting is its weakest task, undertrained vs. Chronos/TimesFM/Kronos which are already real here |
| 18 | `news_first_analysis` | [18-news_first_analysis.md](18-news_first_analysis.md) | decided | confirmed redundant / not required (vinu-news's Section-1 methods already cover this ground); no enhancement proposed, left as-is, still present/runnable |
| 19 | `news_price_causality` | [19-news_price_causality.md](19-news_price_causality.md) | decided | design decided, not yet built; real Granger/Pearson/event-study/XGBoost-classifier stats (not a forecaster, no fallback question); genuinely rigorous — SPY market-factor control, a caught-and-fixed leakage bug, an honestly-reported negative result on direction prediction; timeframes kept as coded (not widened), aggregate tests sliced per-quarter not per-session |
| 20 | `patchtst` | [20-patchtst.md](20-patchtst.md) | decided | design decided, not yet built; genuinely trained-from-scratch (same patch branch LPatchTST uses, standalone); kept specifically as the ablation/control for LPatchTST's comparison, not a standalone candidate — real benchmark (54.1% hit rate, Sharpe 0.86, arXiv:2603.01820) is mediocre on its own |
| 21 | `peer_relative_strength` | [21-peer_relative_strength.md](21-peer_relative_strength.md) | decided | design decided, not yet built; real rolling-correlation/relative-return stats (not a forecaster); main proposal is adding forward-return validation (currently purely descriptive, never checked for predictive value); honest flag — "peers" = watchlist, not curated sector peers |
| 22 | `pnl_attribution` | [22-pnl_attribution.md](22-pnl_attribution.md) | decided | design decided, not yet built; push-fed real trade stats (not a forecaster); proposal adds a per-`artifact_id` breakdown (currently symbol-only, ignores the trade-plan link already in the schema) — checked against Phase 4's separate Calibration system to confirm no duplication; externally validated as standard industry practice |
| 23 | `regime_analysis` | [23-regime_analysis.md](23-regime_analysis.md) | decided | design decided, not yet built; fixes a confirmed lookahead-leak bug (full-sample vol quantile) by adopting the already-validated fix from `news_price_causality/regime_features.py`; adds per-quarter breakdown and normalized transition probabilities |
| 24 | `shock_clustering` | [24-shock_clustering.md](24-shock_clustering.md) | decided | design decided, not yet built; fixes the same lookahead-leak bug class as regime_analysis (full-sample gap z-score); bigger finding — code's "correlation sampled at shock dates" claim is false (verified against `dynamic_covariance`, it's actually a generic unconditional 63-day window), replaced with real co-shock-rate + shock-day correlation, generic correlation dropped as redundant with peer_relative_strength |
| 25 | `shock_personality` | [25-shock_personality.md](25-shock_personality.md) | decided | design decided, not yet built; fixes the same lookahead-leak bug as shock_clustering (independently duplicated code, not shared); surfaces two previously-computed-but-discarded signals (post-shock autocorrelation, per-shock news presence); vol-spike detection widened to 15min/1H/1D, gap detection deliberately kept 1D-only |
| 26 | `tft` | [26-tft.md](26-tft.md) | decided | design decided, not yet built; verified faithful to the real TFT paper (arXiv:1912.09363); corrected a miscited benchmark (58.4% real hit rate, not ~53% claimed) — third instance of the same pattern (lstm, lpatchtst, now tft) from arXiv:2603.01820; confirmed itransformer (09) is clean, closing that open cross-check |
| 27 | `timer_timerxl` | [27-timer_timerxl.md](27-timer_timerxl.md) | decided | design decided, not yet built; **correction to this table** — already genuinely `pretrained` (thuml/timer-base-84m), not fallback_proxy, since the 2026-08-06 wiring pass; spec.yaml title/purpose text is stale and still says "(fallback proxy)" (kronos got the same fix, this one didn't); N raised 24→100, also fixes a sub-patch fallback-trigger quirk |
| 28 | `timesfm` | [28-timesfm.md](28-timesfm.md) | decided | design decided, not yet built; real, correctly-documented pretrained (google/timesfm-2.5-200m-pytorch); genuine native quantile head (unlike Kronos/timer_timerxl) — CI-coverage is primary; found code uses only 256 context vs. the model's own documented 1024 default, and discards 7 of 9 real decile levels — both fixed |
| 29 | `tips_regime_aware_transformer` | [29-tips_regime_aware_transformer.md](29-tips_regime_aware_transformer.md) | decided | design decided, not yet built; verified against the real cited paper (arXiv:2603.16985) — found the code implements a genuinely different, simpler mechanism (2-head autocorrelation gating) than the paper's actual method (multi-teacher distillation across causality/locality/periodicity); rebuilt honestly as "TIPS-inspired," paper's benchmark not carried over; new regime-split metric added |
| 30 | `trend_lifecycle` | [30-trend_lifecycle.md](30-trend_lifecycle.md) | decided | design decided, not yet built; real, well-engineered system (leak-safe walk-forward KNN matching, ATR-adaptive thresholds already used independently); real gap — signals.py's confidence/exit formulas are hand-tuned & unvalidated, same failure pattern as drawdown_deep_dive's original attribution formula; adds a signal-outcome backtest + confidence calibration check; fixes a dead 1W config gap |
| 31 | `trend_session_structure` | [31-trend_session_structure.md](31-trend_session_structure.md) | decided | design decided, not yet built; cleanest angle reviewed — no bugs found (correct dedup, thin-sample guards, no duplicated detection, honest not_applicable scoping already in place); one dependent addition once trend_lifecycle's signal-outcome backtest exists |

**31 angles total** (2 deprecated, still tracked; 29 active). Matches
the real `angles/` directory count after the 4-angle removal — see
`../03-actual-plan-findings/06-models-download.md`.
