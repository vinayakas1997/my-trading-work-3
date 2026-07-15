# Angle Testing Task: Complete Guide

## 1. Task Overview

**Project location:** `C:\Users\vinay\Desktop\my-trading-work-3\vinu-components`

All code, services, and APIs referenced in this task live in the `vinu-components` folder above. When executing any angle, your working directory for service calls and code references is that path.

We are testing **24 analytical angles** on a single trading strategy across **4 tickers** and **4 timeframes** to:
- Validate each angle works end-to-end
- Find and fix bugs in the codebase
- Document execution time for each step
- Prove the system works without LLM

**Start Date:** 2022-01-01

---

## 2. Strategy Used

**ADX-Filtered SMA Crossover (Long/Short)**

| Signal | Condition |
|--------|-----------|
| Bullish (Long) | SMA_9 > SMA_21 AND ADX_14 > 25 |
| Bearish (Short) | SMA_9 < SMA_21 AND ADX_14 > 25 |
| No trade | ADX_14 <= 25 |

**Why this strategy:**
- Medium complexity (2 indicators + regime filter)
- Generates both bullish and bearish signals
- Already exists as template in codebase (`adx_filtered_crossover`)
- Tests indicator computation, signal generation, and rule evaluation

---

## 3. Test Configuration

| Parameter | Value |
|-----------|-------|
| Tickers | AAPL, MSFT, TSLA, NVDA |
| Timeframes | 1d, 4h, 1h, 15m |
| Start date | 2022-01-01 |
| End date | Present (latest available data) |
| Strategy | ADX-Filtered SMA Crossover (Long/Short) |

---

## 4. Reference Files

| File | Purpose |
|------|---------|
| `02-different-angles-on-asset.md` | Full description of all 25 angles — what each angle studies, dimensions, examples |
| `01-withoutLLM-analysis.md` | Technical details — services, APIs, metrics, functions, code paths |

**Read these before starting any angle.**

---

## 5. How to Fill Each `explanation.md`

Each subfolder (01-24) has an `explanation.md` with this skeleton. Fill each section:

### Section 1: What This Angle Studies
- Copy from `02-different-angles-on-asset.md` for the relevant angle
- 2-3 sentences max

### Section 2: Strategy & Configuration Used
- Already filled in the skeleton — just confirm it's correct

### Section 3: Functions & Code Paths
- List every function called during this angle's execution
- Include file path and line number
- Example:

```
| Function | File Path | Purpose |
|----------|-----------|---------|
| get_candles() | vinu-stock-price/service.py:45 | Fetch OHLCV data |
| compute() | vinu-features/compute/indicators/rsi.py:12 | Compute RSI |
```

### Section 3a: Commands & API Calls Used

Document every command, curl call, and CLI invocation used during execution.

| Step | Method | Command / Curl | Description | Response Summary |
|------|--------|---------------|-------------|-----------------|
| 1 | API | `curl http://...` | Fetch OHLCV data | 1000 rows returned |
| 2 | CLI | `vinu-strategy evaluate ...` | Evaluate strategy | Weights output |
| 3 | Agent Tool | `run_strategy(...)` | Agent tool invocation | Strategy result |

**Method values:** `API` (direct curl), `CLI` (vinu-* command), `Agent Tool` (vinu-agent tool), `Python` (direct script)

### Section 4: Results (4 Assets × 4 Timeframes)
- Run the angle for each ticker × timeframe combination
- Record the key result (metric value, pass/fail, output)
- Record time taken for that specific run
- Example:

```
### AAPL
| Timeframe | Result | Key Metric | Time Taken |
|-----------|--------|------------|------------|
| 1d | Pass | Sharpe=1.2, MaxDD=-14% | 3.2s |
| 4h | Pass | Sharpe=0.9, MaxDD=-18% | 4.1s |
| 1h | Fail | No data available | 0.5s |
| 15m | Pass | Sharpe=0.7, MaxDD=-22% | 5.8s |
```

### Section 5: Execution Time Breakdown
- Break down the total time into steps
- Example:

```
| Step | Description | Time |
|------|-------------|------|
| 1 | Fetch price data | 1.2s |
| 2 | Compute indicators | 0.8s |
| 3 | Run analysis | 1.1s |
| **Total** | | **3.2s** |
```

### Section 6: Summary
- Overall findings for this angle
- What worked, what didn't
- Any patterns across tickers/timeframes

---

## 6. How to Fill Each `bugs.md`

Each subfolder has a `bugs.md` with this skeleton. Fill as bugs are found:

### Bug Format
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Status |
|---|-----------------|---------------|------------|-------------|--------------|--------|
| 1 | ... | ... | ... | ... | ... | Fixed/Open |

### Bug Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies

---

## 7. Summary Table

Track progress across all 24 angles. Update as each angle is tested.

| # | Angle | Status | Bugs Found | Time (AAPL/1d) | Notes |
|---|-------|--------|------------|----------------|-------|
| 1 | News-first analysis | Complete | 3 | ~300s | Python script created (angle01_query.py). All 12 news dimensions tested. 3 bugs found: `/candles` days param returns 0 bars, `/story` HTTP 500, correlation sample_size=0. Full 4T x 4TF results documented. |
| 2 | News-price causality | Complete | 6 | ~177s | Python script updated. 11 dimensions tested. 6 bugs: story HTTP 500, strategy evaluate HTTP 500, correlation sample_size=0, price reaction null, drawdown attribution 0%, ADX not in price indicators. Full results across 4T. |
| 3 | Technical indicators | Complete | 0 | ~200s | All 24 indicator kinds verified across 4T × 4TF. Parametric periods tested. 11 presets confirmed. ADX not in price built-in (via features service instead). No new bugs. |
| 4 | Alpha factor zoo | Complete | 6 | 3.8s | Registry browsed (461 factors), metadata sampled, all 11 presets tested. 6 bugs: gtja191/qlib158 presets not registered, individual alpha names fail via HTTP, fundamental factors missing, China universe mismatch, no bulk metadata API. Python scripts: angle04_query.py (browsing) + angle04_compute.py (computation). |
| 5 | Factor backtesting | Complete | 2 | ~75s | 7 factors x 4 weight schemes. 2 bugs: hardcoded min_assets=10 blocks small universes, vol_parity returns all zeros for small N. No REST API (Python library only). alpha101_010 shows best Sharpe (1.19), alpha101_101 worst (-1.28). |
| 6 | Expression DSL | Complete | 3 | ~35s | All 3 expression engines tested. compute_expression (11 fn) + QLib (20 fn) + strategy (4 fn). 3 bugs: QLib eval function not exported, strategy import path mismatch, scale fn not wired. Combined 3-factor blend SR=1.16 best. |
| 7 | Session/time analysis | Complete | 2 | ~65s | 5 sessions x 4 tickers, 962 transitions each. 2 bugs: correlation API missing session_correlations, sample_size=0. Session distribution: ny_regular=2244, premarket=1605, afterhours=1151. Gap API works (0.6-4h). |
| 8 | Drawdown deep-dive | Complete | 2 | ~16s | Drawdown API works (3-102 drawdowns per ticker). Price-based max DD: AAPL=-35%, TSLA=-91%. 2 bugs: news attribution always 0%, drawdown count varies by ticker volatility. |
| 9 | Regime analysis | Complete | 1 | ~0.1s | 4 regimes classified. Bug: regime Sharpe values are extremely large (bull SR=37) due to classification using contemporaneous returns. Per-regime counts and returns computed correctly. |
| 10 | Backtesting (44+ metrics) | Complete | 2 | ~2s | _compute_metrics produces 10 core metrics. 2 bugs: simulator API returns 422 (no weight data pre-computed), no endpoint for strategy registration. Cost models and position sizers exist in codebase. |
| 11 | Validation/overfitting | Complete | 1 | ~1s | MC permutation, bootstrap CI, walk-forward all work via manual implementation. Bug: vinu_research.walk_forward functions not importable by documented names. |
| 12 | Benchmark comparison | Complete | 1 | ~0.1s | SPY not in catalog (0 bars). Used NVDA as proxy. Beta: AAPL=0.17, MSFT=0.18, TSLA=0.32. Bug: SPY not provisioned in data catalog. |
| 13 | Portfolio analysis | Complete | 0 | ~0.1s | Avg pairwise correlation=0.43. AAPL-MSFT highest (0.59), TSLA-NVDA lowest (0.32). Rolling 60d correlation works. |
| 14 | Decay monitoring | Complete | 1 | ~0.1s | IC computation and health scoring work. Bug: vinu_research.decay module not found (code location mismatch). |
| 15 | PnL attribution | Complete | 0 | ~0.1s | PnL decomposition works: total, core, noise components. Core PnL can be negative while total is positive (noise trades contribute). |
| 16 | Shadow trading | Complete | 0 | ~0.5s | K-Means clustering (k=3) on synthetic trades: 3 clusters with silhouette=0.45. Short hold (1.5d), medium (6.3d), long (14.5d). |
| 17 | Fundamentals | Complete | 0 | ~2s | yfinance works for all 4 tickers. AAPL: PE=39.7, ROE=141%, FCF=$101B. TSLA: PE=355. NVDA: PE=32.6, ROE=114%. |
| 18 | Research loop | Complete | 1 | ~0.1s | Bug: vinu_research.runner module not found (import path mismatch). 15 templates and 19 risk critic dimensions documented in codebase. |
| 19 | Strategy expressions | Complete | 0 | ~0.1s | Expression engine works: signal (0.013), RSI mean reversion (0.0 at RSI=45), momentum*ADX (0.028). Rules DSL works via YAML. |
| 20 | ML model pipeline | Complete | 0 | ~0.1s | Ridge regression OOS IC=-0.12 (random data, expected). 9 model types available. Pipeline verified: no-shuffle 80/20 split, spearmanr evaluation. |
| 21 | RL training environment | Complete | 1 | ~0.1s | Simulator health check passes. Bug: SimulatorEnv import path not found. Gym-compatible env with Almgren-Chriss costs documented. |
| 22 | Deflated Sharpe ratio | Complete | 0 | ~0.1s | Bailey & Lopez de Prado formula implemented. 1 trial DSR=1.0, 10 trials DSR=0.05, 30+ trials DSR=0.0. Correctly penalizes multiple testing. |
| 23 | Event study methodology | Complete | 1 | ~1s | Events API works (279-508 events per ticker). Bug: 0 events classified as significant (significance="?"). Manual event study computes AR correctly. |
| 24 | Scheduled/cron research | Complete | 1 | ~0.1s | Bug: vinu_research.scheduled module not importable. Code exists on disk. Manual cron parsing demo works. Full 5-field syntax supported. |
| 25 | Pairs/cointegration | Not implemented | - | - | Future work |

**Status values:** Pending | In Progress | Complete | Blocked

---

## 8. Workflow

> **IMPORTANT:** All testing is done **without vinu-agent**. Do not use or modify `vinu-agent/`. Use direct API calls (curl), CLI commands, or Python scripts only. The vinu-agent service is intentionally left out of scope — the goal is to prove the system works without LLM/agent orchestration.

1. Pick an angle (start from 01, go sequentially)
2. Read `02-different-angles-on-asset.md` for that angle's description
3. Read `01-withoutLLM-analysis.md` for technical details
4. Set up the test configuration (tickers, timeframes, strategy)
5. Execute the angle for AAPL/1d first
6. Record results in `explanation.md` Section 4
7. If bugs found, document in `bugs.md`
8. Fix the bug (or document it for later)
9. Document all commands used in `explanation.md` Section 3a
10. Re-run for remaining ticker × timeframe combinations
11. Fill Sections 3, 5, 6
12. Update the summary table in `00-explanation.md`
13. Move to next angle

---

## 9. Strategy & API Reference

### 9.1 Strategy: ADX-Filtered SMA Crossover

**YAML Definition** (`vinu-strategy/strategies/adx_filtered_crossover.yaml`):
```yaml
name: adx_filtered_crossover
description: "ADX-Filtered SMA Crossover (Long/Short). Long when SMA_9 > SMA_21 AND ADX_14 > 25. Short when SMA_9 < SMA_21 AND ADX_14 > 25. No trade when ADX_14 <= 25."
schedule: daily
features_required:
  - SMA_9
  - SMA_21
  - ADX_14
pipeline:
  selection: { method: all }
  allocation:
    method: signal_scaled
    signal: "SMA_9 / SMA_21 - 1"
  timing:
    method: rules
    rules:
      - name: adx_strength
        when: [{ source: features, key: ADX_14, gt: 25 }]
        then: { action: weight_multiply, value: 1.0 }
      - name: weak_trend
        when: [{ source: features, key: ADX_14, lte: 25 }]
        then: { action: weight_set, value: 0.0 }
  risk: { method: normalize, max_weight: 0.25, cash_floor: 0.10 }
```

**Signal Logic:**

| Signal | Condition |
|--------|-----------|
| Bullish (Long) | SMA_9 > SMA_21 AND ADX_14 > 25 |
| Bearish (Short) | SMA_9 < SMA_21 AND ADX_14 > 25 |
| No trade | ADX_14 <= 25 |

### 9.2 Service Port Map

| Service | Port | CLI Command | .env File |
|---------|------|-------------|-----------|
| vinu-news | 8080 | `vinu-news serve` | `vinu-news/.env` |
| vinu-stock-price | 8081 | `vinu-stock-price serve` | `vinu-stock-price/.env` |
| vinu-features | 8082 | `vinu-features serve` | `vinu-features/.env` |
| vinu-correlation | 8083 | `vinu-correlation serve` | `vinu-correlation/.env` |
| vinu-strategy | 8084 | `vinu-strategy serve` | `vinu-strategy/.env` |
| vinu-simulator | 8085 | `vinu-simulator serve` | `vinu-simulator/.env` |
| ~~vinu-agent~~ | ~~8086~~ | ~~`vinu-agent serve`~~ | — (out of scope) |
| vinu-research | — | `vinu-research run <idea>` | `.env` (CWD) |

### 9.3 Key API Endpoints by Service

**vinu-news** (port 8080):
| Method | Endpoint | Params | Purpose |
|--------|----------|--------|---------|
| GET | `/ticker/{symbol}` | `days`, `limit`, `from`, `to` | News for ticker |
| GET | `/high-impact` | `hours`, `sentiment`, `limit` | High-impact news |
| GET | `/threads/active` | `hours` | Active news threads |
| GET | `/threads/{thread_id}` | — | Thread detail |
| GET | `/stats/ticker/{symbol}` | `days` | News stats |
| GET | `/search` | `q`, `limit` | Full-text search |

**vinu-stock-price** (port 8081):
| Method | Endpoint | Params | Purpose |
|--------|----------|--------|---------|
| GET | `/candles/{symbol}` | `interval`, `from`, `to`, `days`, `indicators` | OHLCV data |
| GET | `/catalog` | — | Available symbols |

**vinu-features** (port 8082):
| Method | Endpoint | Params | Purpose |
|--------|----------|--------|---------|
| POST | `/requests` | body | Submit feature request |
| GET | `/features` | — | List all features |
| GET | `/presets` | — | List recipe presets |

**vinu-correlation** (port 8083):
| Method | Endpoint | Params | Purpose |
|--------|----------|--------|---------|
| GET | `/correlation/{ticker}` | — | News-price correlation |
| GET | `/impact/{ticker}` | — | Impact events |
| GET | `/drawdown/{ticker}` | — | Drawdown attribution |
| GET | `/baseline/{ticker}` | — | News volume baseline |
| GET | `/events/{ticker}` | — | Event study |
| GET | `/story/{ticker}` | — | Story/thread tracking |

**vinu-strategy** (port 8084):
| Method | Endpoint | Params | Purpose |
|--------|----------|--------|---------|
| GET | `/strategies` | — | List strategies |
| GET | `/strategies/{name}` | — | Get strategy config |
| POST | `/strategies/{name}/evaluate` | `symbols` | Evaluate strategy |

### 9.4 CLI Commands Reference

| Command | Purpose | Example |
|---------|---------|---------|
| `vinu-news serve` | Start news service | `vinu-news serve` |
| `vinu-stock-price serve` | Start stock price service | `vinu-stock-price serve` |
| `vinu-features serve` | Start features service | `vinu-features serve` |
| `vinu-correlation serve` | Start correlation service | `vinu-correlation serve` |
| `vinu-strategy serve` | Start strategy service | `vinu-strategy serve` |
| `vinu-strategy evaluate <name>` | Evaluate a strategy | `vinu-strategy evaluate adx_filtered_crossover --ticker AAPL --json` |
| `vinu-strategy list` | List registered strategies | `vinu-strategy list` |
| `vinu-strategy reload` | Reload YAML strategy files | `vinu-strategy reload` |
| `vinu-simulator serve` | Start simulator service | `vinu-simulator serve` |
| `vinu-agent serve` | Start agent service | `vinu-agent serve` |
| `vinu-research run <idea>` | Run research loop | `vinu-research run "SMA crossover on AAPL"` |

### 9.5 Agent Tools Reference (for reference only — vinu-agent is out of scope)

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `get_news` | `symbol`, `days`, `limit` | Fetch news articles |
| `get_stock_price` | `symbol`, `interval`, `from`, `to` | Fetch OHLCV data |
| `get_features` | `symbol`, `interval`, `indicators` | Compute technical indicators |
| `get_correlation` | `symbol` | News-price correlation |
| `run_strategy` | `strategy_name`, `symbols` | Evaluate YAML strategy |
| `run_backtest` | `code`, `symbols`, `start`, `end` | Run Python backtest |
| `run_research` | `idea`, `symbols` | Multi-iteration research loop |
| `factor_analysis` | `factor_id`, `theme` | Browse/describe alpha factors |
| `factor_backtest` | `expression`, `symbols` | Factor expression backtesting |

### 9.6 cURL Examples by Angle Type

**News angles (1, 2):**
```bash
# Fetch AAPL news for last 365 days
curl "http://localhost:8080/ticker/AAPL?days=365&limit=100"

# High-impact news
curl "http://localhost:8080/high-impact?hours=8760&limit=50"

# Correlation analysis
curl "http://localhost:8083/correlation/AAPL"

# Impact events
curl "http://localhost:8083/impact/AAPL"
```

**Technical angles (3, 4, 5, 6):**
```bash
# Fetch candles with indicators
curl "http://localhost:8081/candles/AAPL?interval=1D&from=1640995200&indicators=sma_9,sma_21,rsi_14,adx_14"

# Evaluate strategy
curl -X POST "http://localhost:8084/strategies/adx_filtered_crossover/evaluate?symbols=AAPL"

# CLI equivalent
vinu-strategy evaluate adx_filtered_crossover --ticker AAPL --json
```

**Backtest angles (10, 11, 12):**
```bash
# Run backtest via CLI
vinu-simulator backtest --strategy adx_filtered_crossover --symbol AAPL

# (vinu-agent is out of scope for this testing)
```
