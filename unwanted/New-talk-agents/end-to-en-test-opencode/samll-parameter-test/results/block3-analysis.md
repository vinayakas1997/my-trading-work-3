# Block 3 — Analysis

Cross-service smoke: initial-analysis angles, quant-core strategy evaluate + simulator backtest.

Run date: 2026-08-11 (AAPL complete; TSLA analysis still running server-side at time of writing).

## 3a — initial-analysis
- Endpoint: `POST /analysis/runs` (or equivalent)
- Expected: angles JSON for AAPL / TSLA
- **AAPL: 281 runs completed, 0 errors, 31/31 angles** (arima, backtesting_44_metrics, chronos, cross_attention_gcn_news_price_fusion, dlinear, drawdown_deep_dive, exponential_smoothing, garch, itransformer, kalman_filters, kronos, lag_llama, lpatchtst, lstm, ml_model_pipeline, moirai, moment, news_first_analysis, news_price_causality, patchtst, peer_relative_strength, pnl_attribution, regime_analysis, shock_clustering, shock_personality, tft, timer_timerxl, timesfm, tips_regime_aware_transformer, trend_lifecycle, trend_session_structure).

| Ticker | Interval | Status | Angles present |
|---|---|---|---|
| AAPL | all (281 runs, 31 angles × timeframes) | PASS | 31/31 completed, 0 errors |
| TSLA | in progress | IN PROGRESS | 19/281 runs done (arima, backtesting_44_metrics) at last check |

Server-side compute continues after client disconnect; ~1h30m for a full ticker.

## 3b — quant-core strategy evaluate
- Strategy: `e2e_easy_sma_crossover`
- Expected: evaluation output with positions/signals

| Ticker | Interval | Status | Signals produced |
|---|---|---|---|
| AAPL | 1D | PASS (31.41s incl. angle fetch) | weight AAPL +0.25, signal_value 0.0, run_id e2e_easy_sma_crossover_20260811_170930 |
| TSLA | 1D | PENDING (after TSLA analysis completes) | |

Note: `evaluate` computes current-day weights only; `bear_exit` rule trace reports `FAIL: key not found in context` for `regime_analysis.regime` because no angle context is passed to evaluate (angles fetched only when strategy declares `angles_required` — declared, but rule trace shows the angle signal missing at evaluate time; see DEV).

## 3c — simulator backtest
- Strategy: `e2e_easy_sma_crossover`
- Expected: backtest metrics (returns, sharpe, etc.)
- Used `/simulator/simulate/custom` with inline SMA-9/21 crossover (pipeline's deterministic path) — the standard `/simulator/simulate` requires a pre-existing **historical daily weight series** in strategy weight storage, which `evaluate` does not produce for past dates.

| Ticker | Interval | Status | Metrics present | run_id present |
|---|---|---|---|---|
| AAPL | 1D | PASS (1.62s) | total_return +4.21%, Sharpe 0.538, MaxDD -6.20%, 8 trades, 127 equity points | b94b2367-6724-4009-8664-e3d3cfd430ff |

Backtest metrics (AAPL custom backtest): total_return 0.0421, cagr 0.0860, annual_vol 0.1847, sharpe 0.5382, sortino 0.5489, max_drawdown -0.0620, calmar 1.387, win_rate 0.333, profit_factor 1.127, annual_turnover 16.07.

## Evidence
- `evidence/03-analysis/simulator-aapl.json`
- `evidence/03-analysis/strategy-evaluate-aapl.json`
- `evidence/03-analysis/deterministic-aapl.json` (per-stage timings: features 0.04s, analysis 95.38s, strategy 31.41s, simulator 1.62s)

## Deviations / Issues
- Strategy registry loads empty at startup (strategies dir unseeded) → FIXED by seeding `/data/strategy/strategies` from image + container restart. See `../issues/`.
- `/simulator/simulate` requires a historical weight series; deterministic backtest path uses `/simulate/custom`. See `../deviations/`.
