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

## Status table

| # | Angle | File | Status | Notes |
|---|-------|------|--------|-------|
| 01 | `arima` | [01-arima.md](01-arima.md) | not-discussed | |
| 02 | `backtesting_44_metrics` | [02-backtesting_44_metrics.md](02-backtesting_44_metrics.md) | not-discussed | |
| 03 | `chronos` | [03-chronos.md](03-chronos.md) | not-discussed | pretrained foundation model |
| 04 | `cross_attention_gcn_news_price_fusion` | [04-cross_attention_gcn_news_price_fusion.md](04-cross_attention_gcn_news_price_fusion.md) | not-discussed | |
| 05 | `dlinear` | [05-dlinear.md](05-dlinear.md) | not-discussed | |
| 06 | `drawdown_deep_dive` | [06-drawdown_deep_dive.md](06-drawdown_deep_dive.md) | not-discussed | |
| 07 | `exponential_smoothing` | [07-exponential_smoothing.md](07-exponential_smoothing.md) | not-discussed | |
| 08 | `garch` | [08-garch.md](08-garch.md) | not-discussed | |
| 09 | `itransformer` | [09-itransformer.md](09-itransformer.md) | not-discussed | |
| 10 | `kalman_filters` | [10-kalman_filters.md](10-kalman_filters.md) | not-discussed | |
| 11 | `kronos` | [11-kronos.md](11-kronos.md) | not-discussed | pretrained foundation model |
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
