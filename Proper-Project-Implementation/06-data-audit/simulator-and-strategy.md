# Data audit: vinu-simulator and vinu-strategy (one container, `quant-core-api`)

Checked 2026-10-08 on the running stack (`/data/simulator` 55 MB, `/data/strategy` 304 KB).

## What triggers them
- **Simulator** (`POST /simulator/simulate`, `/simulate/custom`): runs one backtest of a strategy over bars and stores the result. Called by research (every loop iteration, every sweep point), the agent, and scripts.
- **Strategy service** (`/strategy/strategies/{name}/evaluate`, `/precondition-check`): turns a YAML strategy (selection, allocation, timing, risk) into target weights, using features, angles and the analysis "correlation" routes. Called by live (precondition check) and the agent.

## Data items

### M1 Simulation runs  `simulator_meta.db: simulation_runs` (1,022) + `simulations/<xx>/<run_id>/` (5 files each: `equity.parquet`, `trades.parquet`, `weights.parquet`, `run_card.json`, `run_card.md`)
- **Format:** config JSON (dates, capital, costs 0.1% + 0.05% slippage, `allow_short`), metrics JSON (return, CAGR, Sharpe, Sortino, drawdown, win rate, VaR ...), benchmark metrics. 929 runs are `UserStrategy` (research candidates), 93 are `Strategy`. Made 2026-10-06 to 2026-10-07; 52 MB; nothing is pruned (`DELETE /runs` exists but is not scheduled).
- **Access:** `GET /simulator/runs`, `/results/{id}`, `/metrics`, `/equity`, `/weights`, `/trades`.
- **Consumers (found in code):** research (backtest for every iteration; `results` for validation), agent (runs/results tools, comparison), portfolio (`results`: the strategy's equity returns feed the weights and the capital allocator's win/loss statistics).
- **Verdict:** `used well`. One serious mismatch: **1,019 of 1,022 runs (99.7%) were simulated with shorting allowed** (research's `allow_short` defaults to true) while the system's mandate is long-only. A strategy that earns part of its Sharpe on the short side is judged on money it cannot make (DA-M1).

### M2 Simulation catalog  `simulation_catalog` (0 rows), `simulation_run_symbols` (1,022)
- The catalog table is never filled. Per-symbol rows are filled. **Verdict:** `empty` (DA-M2).

### M3 Strategy registry  `strategy/meta.db: strategy_registry` (11 rows), `strategy_runs` (0)
- 11 YAML strategies seeded from the image into `/data/strategy/strategies`: adx_filtered_crossover, e2e_easy_sma_crossover, e2e_medium_trend_vol_filter, ma_crossover, news_aware_momentum, paper_smoke_test, rsi_mean_reversion, trend_pullback_long (plus 15m, 1h, 4h).
- **Access:** `GET /strategy/strategies`, `/weights`, `/runs`. **Consumers:** live (precondition check, 48 mentions), portfolio (lists strategies; YAML ones get no capital by default since P53), agent (4 files), screener (1).
- **Evaluations ever run: 0** (`strategy_runs` empty, `weights/` empty, `precondition_state` empty). **Verdict:** `idle` (DA-M3).

### M4 The one place news reaches a strategy: `news_aware_momentum.yaml`
- Its timing rules read `correlation.high_impact_bullish_events`, `granger_causes_prices`, `high_impact_bearish_events`, `drawdown_count` from the analysis routes (`/analysis/impact`, `/correlation`, `/drawdown`), which come from the `news_price_causality` and `drawdown_deep_dive` angles.
- **Real call for AAPL today:** `/analysis/impact/AAPL` returned `high_impact_bullish_events 0, high_impact_bearish_events 0, event_count 1` and that one event is a placeholder row ("status", `event_count 0`); `/analysis/correlation/AAPL` returned `news_return_corr None, sample_size 0`. AAPL has 7,976 articles. Cause found in the chain below. So the rules above read zeros and never fire (DA-M4).

## Chain found while checking M4 (news -> angle -> strategy)
1. `GET /news/ticker/{symbol}` attaches the price reaction to every article. That makes each page call stock-price for candles, so one request page costs about 8 s; AAPL's 7,941 articles took 137 s to read, with a transient HTTP 500 on the way (retried).
2. initial-analysis fetches the articles once per run. If the fetch fails after its retries, the runner stores `[]`, flags `news_fetch_failed` only in the immediate reply, and still saves the run as "completed".
3. The angle then writes one placeholder row (`type: status`, `event_count 0`). The newest completed run is the one that is read, so this placeholder **replaces** the earlier real result. For `news_price_causality`, 36 of the 300 latest results (12%) replaced an earlier richer result with a near-empty one (AAPL's 1-minute result fell from 1,123 rows on 2026-10-06 to 1 row on 2026-10-07).
4. `/analysis/impact` and `/analysis/correlation` read that placeholder, so the strategy and the research context see "no news effect".
Root causes sit in three places: the slow bulk read of news (stock-price speed and always-on reaction), the runner saving a failed fetch as a completed run, and "latest wins" with no check that the new result is not worse. Listed as chain C1 in `findings.md`.
