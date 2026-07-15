# vinu-components: Complete Analysis Without LLM

> What can this system do if LLM is disabled? Answer: Everything except automated idea generation and natural-language summaries. 25 analytical angles, 250+ sub-dimensions, all without LLM.

---

## Architecture Overview

The vinu-components is a **9-microservice trading research platform**. Each service is independent, communicates via HTTP, and can operate without any LLM dependency.

```
vinu-stock-price ──OHLCV──> vinu-simulator ──results──> vinu-research
vinu-news ──articles──> vinu-correlation ──signals──> vinu-strategy
vinu-features ──461 factors──> vinu-strategy ──weights──> vinu-simulator
vinu-agent ──17 tools──> All services via HTTP
```

### Service Inventory

| # | Service | Purpose | LLM Required? |
|---|---------|---------|---------------|
| 1 | vinu-lib | Shared utilities (DB, config, security, rate limiting) | No |
| 2 | vinu-stock-price | OHLCV data from 5 providers, Parquet storage, gap validation | No |
| 3 | vinu-news | News ingestion, 15-stage enrichment pipeline, threading | Partial (LLM analysis optional) |
| 4 | vinu-features | 461+ alpha factors, 23 indicator kinds, expression parser | No |
| 5 | vinu-correlation | Pearson, Granger, lag analysis, impact, drawdown attribution | No |
| 6 | vinu-strategy | YAML-based 4-stage pipeline, rules DSL, expression engine | No |
| 7 | vinu-simulator | Backtesting with market impact, 44+ metrics, validation | No |
| 8 | vinu-research | Automated research loop, walk-forward, decay monitoring | Partial (LLM enhances critic) |
| 9 | vinu-agent | 17 callable tools for interactive research | No |

---

## 1. DATA LAYER (No LLM)

### 1.1 vinu-stock-price

**Providers (5):**
- Alpaca Markets API
- Polygon.io API
- Yahoo Finance (direct)
- yfinance library
- TuShare (China markets)

**Capabilities:**
- 7 intervals: 1m, 5m, 15m, 30m, 1h, 4h, 1d
- Parquet archive storage
- Gap validation (counts missing 1m bars during NYSE session 9:30-16:00 ET)
- Live ingestion cycle
- Historical backfill (year-by-year, parallel across symbols)
- Provider fallback chains: US equity (alpaca->polygon->yahoo), Crypto (alpaca->yahoo)
- Adjusted price support
- Indicator computation at query time (SMA, RSI, MACD, daily_return, volatility_20d)

**API Endpoints:**
```
GET /candles/{symbol}?interval=1d&from_ts=...&to_ts=...&indicators=sma_20,rsi_14
GET /catalog/{symbol}
GET /settings / PATCH /settings
GET /health
```

### 1.2 vinu-news

**Ingestion Sources:**
- RSS feeds (multiple tiers, configurable)
- Yahoo Finance news
- Financial Modeling Prep (FMP)
- Alpaca news

**15-Stage Enrichment Pipeline (No LLM):**

| Stage | What It Does |
|-------|-------------|
| 1. Validation | Validates raw article dicts for required fields |
| 2. URL Dedup | Drops duplicate URLs within a batch |
| 3. Summary Cleaning | Strips HTML, collapses whitespace, truncates to 300 chars |
| 4. Priority Classification | FLASH > URGENT > BREAKING > ROUTINE (keyword waterfall) |
| 5. Sentiment Scoring | 100+ financial phrases + 72 sentiment words → BULLISH/BEARISH/NEUTRAL |
| 6. Impact Classification | HIGH/MEDIUM/LOW from priority + sentiment magnitude |
| 7. Category Refinement | 8 categories: EARNINGS, CRYPTO, DEFENSE, ECONOMIC, MARKETS, ENERGY, TECH, GEOPOLITICS |
| 8. Ticker Extraction | Regex + alias DB → up to 5 tickers per article |
| 9. Language Detection | Script-based: en, ja, ko, zh, ru, ar, hi |
| 10. Threat Classification | 30+ patterns: CRITICAL/HIGH/MEDIUM/LOW across conflict/market/cyber/regulatory/natural |
| 11. Source Credibility | Flags state media (10 sources) and caution sources (4 sources) |
| 12. Ticker Dominance | Normalized weights for multi-ticker articles (headline 3x, summary 1x, position 2x) |
| 13. NER Extraction | Named entities from headline + summary |
| 14. Cosine Dedup | Cluster near-duplicate articles by cosine similarity |
| 15. Price Reaction | 1h and 1d price change after each article (cached) |

**Post-Enrichment:**
- Lead article selection per cluster
- Thread tracking (group related articles into evolving stories)
- Thread intensity score (articles per hour)

**Query Methods:**
- `get_ticker_news(symbol, days)` — ticker-specific with price reaction
- `get_high_impact(hours, sentiment)` — high-impact articles filtered
- `get_active_threads(hours)` — evolving story threads
- `get_thread_detail(thread_id)` — thread with all articles
- `get_ticker_stats(symbol, days)` — daily stats
- `search(query)` — full-text search
- `get_watchlist_news(days)` — all watchlist tickers

### 1.3 vinu-features

**23 Indicator Kinds (Parametric, period 1-500):**

| Category | Indicators |
|----------|-----------|
| Trend | SMA, EMA, MACD, MACD Signal, ADX, Supertrend, Aroon |
| Momentum | RSI, CCI, Williams %R, Momentum N, Rate of Change |
| Volatility | ATR, Bollinger Bands (upper/mid/lower), Volatility 20d |
| Volume | OBV, VWAP, Volume Ratio, Chaikin Money Flow |
| Price Action | Daily Return, High-Low Spread, Open-Close Return, Stochastic |

**11 Preset Recipe Packs:**

| Preset | Description |
|--------|------------|
| basic_ta | sma_20, rsi_14, daily_return |
| swing_basic | sma_20, sma_100, rsi_14, volatility_20d |
| momentum | sma_10, sma_50, rsi_14, macd, macd_signal |
| trend_pack | sma_20, sma_50, ema_12, ema_26, macd, macd_signal, adx_14 |
| volatility_pack | atr_14, bb_upper, bb_mid, bb_lower, volatility_20d |
| volume_pack | obv, volume_ratio_20, cmf_20 |
| mean_reversion_pack | rsi_14, bb_upper, bb_mid, bb_lower, stoch_k, stoch_d |
| full_ta | All features combined |
| alpha101 | WorldQuant Alpha101 factors |
| alpha158 | Qlib Alpha158 factors |
| alpha360 | Extended alpha factor set |

**461+ Alpha Factors Across 5 Families:**

| Zoo | Count | Origin |
|-----|-------|--------|
| alpha101 | ~100 | WorldQuant |
| gtja191 | ~191 | GTJA research |
| qlib158 | ~158 | Microsoft Qlib |
| academic | varies | Published papers |
| fundamental | varies | Financial statement ratios |

**13 Factor Themes:**
momentum, reversal, volatility, value, growth, quality, size, liquidity, sentiment, seasonality, volume, microstructure, other

**Each factor has metadata:**
- id, theme, formula_latex, columns_required, universe, frequency, decay_horizon, min_warmup_bars

**Expression DSL (18 operators):**
rank, zscore, scale, ts_rank, ts_corr, ts_cov, ts_argmax, ts_argmin, delta, decay_linear, signed_power, safe_div, vwap, ts_sum, ts_mean, ts_std, ts_max, ts_min

**Example expressions:**
```
rank(alpha101_001) * zscore(gtja191_005)
ts_mean(alpha101_001 - alpha101_002, 10) / ts_std(alpha101_001, 10)
SMA_9 / SMA_21 - 1
max(0, (30 - RSI_14) / 30) - max(0, (RSI_14 - 70) / 30)
```

### 1.4 vinu-correlation

**Statistical Analysis Engine:**

| Analysis | What It Proves |
|----------|---------------|
| Pearson correlation | Does article count correlate with price returns? (with p-value, 95% CI) |
| Sentiment-return correlation | Does sentiment score predict returns? |
| News volume-|return| correlation | Does news volume predict volatility? |
| Granger causality | Does news volume statistically *cause* price movements? (SSR F-test) |
| Lag analysis | At what delay (0/15/30/60 min) does news most strongly predict price? |
| Event study | Abnormal return in 30min window after news event (t-test significance) |
| CAR | Cumulative abnormal return over event window |
| Session-level correlation | Does news correlate differently in London vs NY Regular vs Premarket? |
| Drawdown detection | Peak-to-trough drops exceeding threshold |
| Drawdown attribution | % caused by news events vs market beta vs unexplained |
| News volume baseline | Z-scores per session — is today's news abnormally high? |
| Session transition analysis | Price gaps and news correlation at session boundaries |
| Premarket gap | Time gap between last premarket article and market open |

**5 Trading Sessions (DST-aware):**
- closed, london, ny_premarket, ny_regular, ny_afterhours

---

## 2. STRATEGY LAYER (No LLM)

### 2.1 YAML Strategy Definition

**4-Stage Pipeline:**

| Stage | Methods | Parameters |
|-------|---------|------------|
| Selection | `all`, `threshold`, `top_n` | `on: <field>`, `min: <float>`, `n: <int>` |
| Allocation | `equal`, `signal_scaled` | `signal: <expression>` (math DSL) |
| Timing | `none`, `rules` | Rules DSL: `when` conditions + `then` actions |
| Risk | `normalize`, `none` | `max_weight`, `cash_floor`, `max_short_weight`, `allow_short` |

**Rules DSL:**
- 8 condition operators: eq, neq, gt, gte, lt, lte, in, between
- 2 condition sources: features, correlation
- 4 action types: weight_add, weight_subtract, weight_multiply, weight_set
- Rules evaluated sequentially (order matters)

**Expression Engine (Safe AST-based):**
- Variables from context dict (case-insensitive)
- Operators: +, -, *, /, **, %
- Functions: max, min, abs, round
- Booleans: True = 1.0, False = 0.0

### 2.2 Strategy Templates (15 Built-in)

| # | Template | Regime | Complexity | Key Indicators |
|---|----------|--------|------------|----------------|
| 1 | MA Crossover | trending | 1 | SMA fast/slow |
| 2 | Triple MA Crossover | trending | 2 | SMA fast/mid/slow |
| 3 | MACD Crossover | trending | 2 | EMA fast/slow/signal |
| 4 | VWAP Crossover | intraday, trending | 1 | VWAP |
| 5 | RSI Mean Reversion | ranging, mean_reverting | 1 | RSI |
| 6 | Bollinger Bands Mean Reversion | ranging, mean_reverting | 1 | SMA, std |
| 7 | Z-Score Mean Reversion | ranging, mean_reverting | 2 | SMA, std, z-score |
| 8 | Momentum (ROC) | trending | 1 | ROC / close shift |
| 9 | Rate of Change Momentum | trending | 2 | ROC threshold |
| 10 | Price Breakout | volatile, trending | 1 | Rolling high/low |
| 11 | ATR Volatility Breakout | volatile | 2 | ATR |
| 12 | Supertrend | trending | 2 | ATR, hl_avg |
| 13 | ADX-Filtered Crossover | trending | 2 | SMA, ADX |
| 14 | Volume-Confirmed Breakout | trending, volatile | 2 | Rolling high, volume |
| 15 | Momentum/Mean Reversion Hybrid | adaptive | 3 | ATR (regime), SMA, z-score |

### 2.3 Example Strategies

**MA Crossover:**
```yaml
features_required: [SMA_9, SMA_21]
pipeline:
  selection: { method: all }
  allocation: { method: signal_scaled, signal: "SMA_9 / SMA_21 - 1" }
  timing: { method: none }
  risk: { method: normalize, max_weight: 0.25, cash_floor: 0.10 }
```

**RSI Mean Reversion:**
```yaml
features_required: [RSI_14]
pipeline:
  allocation: { method: signal_scaled, signal: "max(0, (30 - RSI_14) / 30) - max(0, (RSI_14 - 70) / 30)" }
```

**News-Aware Momentum:**
```yaml
features_required: [MOM_20, ADX_14]
correlation_required: [impact, granger, drawdown]
pipeline:
  selection: { method: threshold, on: MOM_20, min: 0.0 }
  timing:
    method: rules
    rules:
      - name: news_bullish_boost
        when:
          - { source: correlation, key: high_impact_bullish_events, gt: 1 }
          - { source: correlation, key: granger_causes_prices, eq: true }
          - { source: features, key: ADX_14, gt: 25 }
        then: { action: weight_multiply, value: 1.20 }
```

---

## 3. BACKTESTING LAYER (No LLM)

### 3.1 Backtest Engine Features

- **T+1 execution**: Signals shifted forward by 1 day (no look-ahead bias)
- **Sell-before-buy order**: Sells executed first to free cash
- **Deviation threshold**: Only rebalances when portfolio deviation > threshold (default 5%)
- **Short selling support**: Optional, with daily borrow costs
- **Gym-like RL environment**: `SimulatorEnv` for reinforcement learning

### 3.2 Cost Models

| Model | Description | Parameters |
|-------|-------------|-----------|
| FlatCostModel | Simple percentage-based | cost_pct (0.1%), slippage_pct (0.05%) |
| AlmgrenChrissCostModel | Volume-aware market impact | fixed_cost_pct, market_impact_coeff, market_impact_exp (0.5 square-root law), slippage_pct, missing_volume_impact_pct |

**Almgren-Chriss Formula:**
```
participation_rate = min(shares / volume, 1.0)
impact = price * shares * coeff * (participation_rate ^ exponent)
```

### 3.3 Position Sizers

| Sizer | Description | Parameters |
|-------|-------------|-----------|
| FixedSizer | Strategy weights as-is | None |
| VolTargetSizer | Scale exposure to target constant annual vol | target_annual_vol (15%), lookback_days (20), max_leverage (1.0) |
| FractionalKellySizer | Kelly criterion sizing | kelly_fraction (0.25 = quarter Kelly), lookback_days (60), max_leverage (1.0) |

### 3.4 Performance Metrics (44+)

**Core Performance (10):**

| Metric | Description |
|--------|-------------|
| total_return | Cumulative return |
| cagr | Compound annual growth rate |
| annual_volatility | Annualized standard deviation |
| sharpe_ratio | Risk-adjusted return |
| sortino_ratio | CAGR / downside deviation |
| max_drawdown | Worst peak-to-trough decline |
| calmar_ratio | CAGR / abs(max drawdown) |
| win_rate | Fraction of positive-return days |
| skewness | Return distribution skewness |
| kurtosis | Return distribution kurtosis |

**Extended Risk (11):**

| Metric | Description |
|--------|-------------|
| var_95 | 5th-percentile daily return (VaR 95%) |
| var_99 | 1st-percentile daily return (VaR 99%) |
| cvar_95 | Conditional VaR (expected shortfall) |
| tail_ratio | 95th / 5th percentile ratio |
| max_dd_duration_days | Longest drawdown period |
| avg_drawdown | Mean drawdown depth |
| recovery_time_days | Days to recover from max drawdown |
| profit_factor | Sum(gains) / abs(sum(losses)) |
| avg_win_pct | Average winning day return |
| avg_loss_pct | Average losing day return |
| win_loss_ratio | abs(avg_win / avg_loss) |

**Statistical Significance (5):**

| Metric | Description |
|--------|-------------|
| sharpe_standard_error | sqrt((1 + 0.5*SR^2) / n) |
| sharpe_p_value | Two-tailed p-value for Sharpe != 0 |
| sharpe_ci_95_low | Lower bound of 95% CI |
| sharpe_ci_95_high | Upper bound of 95% CI |
| hit_rate | Fraction of positive days |

**Benchmark-Relative (7):**

| Metric | Description |
|--------|-------------|
| beta | Regression beta vs benchmark |
| alpha | Jensen's alpha |
| tracking_error | Volatility of excess returns |
| information_ratio | Alpha / tracking error |
| market_correlation | Pearson correlation with benchmark |
| up_capture | Strategy return on up-benchmark days |
| down_capture | Strategy return on down-benchmark days |

**Activity (1):**
- annual_turnover: Total traded value / avg portfolio value

### 3.5 Validation Methods

| Method | What It Tests |
|--------|--------------|
| Monte Carlo permutation | 1000 shuffles of trade PnL → p-value for Sharpe |
| Bootstrap Sharpe CI | 1000 bootstrap samples → 95% CI for true Sharpe |
| Walk-forward consistency | N windows, return and Sharpe per window |
| Deflated Sharpe ratio | Bailey & Lopez de Prado (2014) — adjusts for multiple testing |
| Holdout validation | Trailing 20% of data never seen by refinement |

**Overfitting Verdict:**
- LOW risk: Sharpe gap <= 0.3
- MODERATE risk: 0.3 < gap <= 0.5
- HIGH risk: gap > 0.5

### 3.6 Attribution Analysis

| Method | What It Measures |
|--------|-----------------|
| Per-symbol stats | Count, win_rate, total_pnl, avg_pnl, avg_win, avg_loss |
| Per-exit-reason stats | PnL grouped by exit reason |
| Beta regression | Alpha, beta, R², correlation, tracking error, information ratio |
| Regime analysis | Per-regime: count, total_return, avg_return, std_return, sharpe, win_rate |
| PnL decomposition | Core PnL, noise trades, early exit, late exit, overtrading |

### 3.7 Run Card Generation

Generates JSON + Markdown containing:
- Backtest configuration
- Reproducibility hashes (config, strategy code)
- All performance metrics
- Benchmark comparison
- Validation results (Monte Carlo, Bootstrap, Walk-Forward)
- Attribution (by symbol, by benchmark, by regime)
- Artifact file list with SHA256 checksums

---

## 4. RESEARCH LAYER (No LLM)

### 4.1 Research Loop (Rule-Based Critic)

**Iterations (up to max_iterations):**
1. Generate strategy code (template-based)
2. Static AST verification (catches hallucinated columns)
3. Run backtest
4. Risk critic evaluation (19 dimensions)
5. Post-backtest weight holding check
6. Verdict: PASS / REFINE / STOP

**Risk Critic Checks (19 Dimensions):**

| # | Check | Threshold |
|---|-------|-----------|
| 1 | Max drawdown | < -15% = concern |
| 2 | Sharpe ratio | < 0.5 = concern |
| 3 | Win rate | < 40% = concern |
| 4 | London session drawdown clustering | >= 2 drawdowns |
| 5 | CVaR 95% | < -3% = concern |
| 6 | Recovery time | > 120 days = concern |
| 7 | Annual turnover | > 2000% = concern |
| 8 | Sharpe p-value | > 0.05 = not significant |
| 9 | Profit factor | < 1.0 = losing money |
| 10 | VaR 95% | < -4% = concern |
| 11 | Alpha vs benchmark | < 0 = underperforming |
| 12 | Information ratio | 0-0.5 = weak |
| 13 | Down capture | > 120% = losing more than market |
| 14 | Excess CAGR | < 0 = underperforming |
| 15 | Passive outperformance | Benchmark CAGR > strategy CAGR |
| 16 | Trade count | < 30 = insufficient sample |
| 17 | Sharpe improvement | Must improve by > 0.05 between iterations |
| 18 | Max drawdown threshold | < -25% triggers STOP |
| 19 | Iteration stall | Sharpe < 0.3 after iteration 3 = STOP |

**Verdict Logic:**
- PASS: Sharpe >= 1.5 AND MaxDD >= -30% AND trade count >= 30
- STOP: Sharpe < 0.3 after 3 iterations, or improvement stalls
- REFINE: Everything else

**Auto-Injected Filters (from critique suggestions):**
- ADX filter (skip if ADX < 20)
- Session exclusion (skip London)
- News cooldown (skip 60min after high-impact news)
- Volatility guard (skip if ATR/close > 5%)

### 4.2 Walk-Forward Validation

**Configuration:**
- method: expanding or sliding window
- train_pct / test_pct / val_pct
- n_windows (default 3)
- min_train_days (252 = 1 year)
- gap_days between train and test (5)

**Per-Window Metrics (both IS and OOS):**
- sharpe_ratio, max_drawdown, win_rate, cagr, total_return

**Aggregated Dimensions (12):**
- Median IS/OOS Sharpe and gap
- Median IS/OOS MaxDD and gap
- Median IS/OOS Win Rate and gap
- Standard deviation of each metric across windows
- losing_window_fraction (% of OOS windows with negative return)

### 4.3 Decay Monitoring

**Metrics (4):**
- ic_ratio: Rolling IC / baseline IC
- rolling_ir: Mean IC / StdDev IC
- ic_positive_ratio: Fraction of periods with positive IC
- rolling_sharpe: Mean of rolling sharpes

**Health Status (4 levels):**
- HEALTHY: score >= 3
- WARNING: 0 <= score < 3
- DECAYED: -5 <= score < 0
- CRITICAL: score < -5

**State Machine (6 states):**
```
CREATED → BENCHING → ACTIVE → MONITORING → DECAYED → DISABLED
                            ↑                ↓
                            └── (HEALTHY) ───┘
```

### 4.4 Benchmark Comparison

**Standalone Benchmark Metrics (7):**
- total_return, CAGR, annual_volatility, sharpe_ratio, sortino_ratio, max_drawdown, win_rate

**Relative Comparison (10):**
- beta, alpha, tracking_error, information_ratio, up_capture, down_capture, market_correlation, relative_max_drawdown, excess_cagr, side-by-side table

### 4.5 Portfolio Analysis

**Dimensions:**
- Full pairwise correlation matrix
- Average pairwise correlation
- Raw vs beta-hedged Sharpe, MaxDD, annual vol
- Rolling beta (causally shifted by 1 day)
- Beta-neutral hedge overlay

### 4.6 Hypothesis Registry

- Persistent JSON-backed CRUD
- Status lifecycle: exploring → testing → validated/rejected/monitoring
- Goal criteria (e.g., Sharpe > 1.0, MaxDD > -20%)
- Backtest linking

### 4.7 Shadow Trading

- FIFO trade pairing into round-trips
- K-Means clustering to identify rule clusters (3-5 rules)
- Auto-extracted entry/exit conditions
- PnL decomposition: core, noise, early exit, late exit, overtrading

---

## 5. AGENT TOOLS (17 Tools, No LLM Required)

| # | Tool | What It Does | Service Called |
|---|------|-------------|---------------|
| 1 | backtest_tool | Run custom Python strategy backtest | vinu-simulator |
| 2 | strategy_tool | Evaluate YAML strategy | vinu-strategy |
| 3 | stock_price_tool | Fetch OHLCV data | vinu-stock-price |
| 4 | news_tool | Query news articles | vinu-news |
| 5 | features_tool | Compute technical indicators | vinu-features |
| 6 | correlation_tool | News-price correlation analysis | vinu-correlation |
| 7 | factor_backtest_tool | Factor-based backtesting | vinu-features |
| 8 | factor_analysis_tool | Browse/describe 461+ factors | vinu-features |
| 9 | fundamentals_tool | yfinance fundamentals | yfinance (direct) |
| 10 | portfolio_tool | Alpaca paper trading positions/orders | Alpaca API |
| 11 | trade_tool | Submit/cancel orders | Alpaca API |
| 12 | research_tool | Full research loop | vinu-research |
| 13 | web_search_tool | DuckDuckGo web search | DuckDuckGo API |
| 14 | session_search_tool | Search past conversations | Local storage |
| 15 | remember_tool | Persistent cross-session memory | Local storage |
| 16 | load_skill_tool | Load documentation | Local files |
| 17 | compact_tool | Context compaction | Internal |

---

## 6. WEB UIs (3 Dashboards)

### vinu-strategy UI
- Strategy browser (sidebar list)
- Pipeline viewer (S → A → T → R stages)
- Weights table (latest 20 records, color-coded)
- Runs history (run ID, symbol, timestamp, status)
- Live "Evaluate Now" button

### vinu-features UI
- Request submission form (symbol, time range, features, conditions)
- Indicator catalog browser
- Preset recipe browser
- Computation lifecycle tracking

### vinu-correlation UI
- Correlation proof visualization (bars with CI and p-values)
- Impact events table (headline, sentiment, price deltas at 5m/15m/30m/1h)
- Drawdown attribution cards (news-driven %, market beta %, unexplained %)
- News volume baseline (z-scores per session)

---

## 7. REST API ENDPOINTS

### vinu-strategy (11 endpoints)
```
GET  /health
GET  /settings
GET  /strategies
GET  /strategies/{name}
POST /strategies/{name}/evaluate
GET  /weights
DELETE /weights/{strategy}
GET  /runs
DELETE /runs
DELETE /runs/{run_id}
GET  /docs/yaml-reference
```

### vinu-features (8 endpoints)
```
GET  /health
GET  /presets
POST /requests
GET  /requests
GET  /requests/{id}
GET  /requests/by-title/{title}
POST /requests/{id}/run
DELETE /requests/{id}
GET  /features
GET  /features/{symbol_or_kind}
```

### vinu-correlation (10 endpoints)
```
GET  /health
GET  /settings
GET  /impact/{ticker}
GET  /events/{ticker}
GET  /correlation/{ticker}
GET  /correlation/batch
GET  /drawdown/{ticker}
GET  /baseline/{ticker}
GET  /story/{ticker}
GET  /gap/{ticker}
```

---

## 8. ADDITIONAL NON-LLM CAPABILITIES (6 Found in Audit)

These capabilities exist in the codebase but were not covered in the original analysis. All 6 work without LLM.

### 8.1 ML Model Pipeline (Traditional ML)

**Location:** `vinu-features/compute/ml_models/`

**9 Supported Algorithms:**
- XGBoost
- Random Forest
- Ridge Regression
- Lasso Regression
- LightGBM
- CatBoost
- Elastic Net
- Linear Regression
- Logistic Regression

**Pipeline Flow:**
1. Load features parquet (461 alpha factors as input)
2. Generate forward-return labels (configurable horizon)
3. Build X/y matrices
4. Split 80/20 time-ordered (no shuffle — prevents look-ahead)
5. Train specified model
6. Compute out-of-sample IC (Spearman rank correlation)
7. Write `scores.parquet` with `ml_score` and `ml_oos` columns
8. Write `oos_metrics.json`

**Auto Selection:** `select_best()` picks model with highest OOS IC across all candidates.

**Key Files:**
- `runner.py` — orchestrator
- `registry.py` — model dispatch + `select_best()`, `oos_ic()`
- `labels/labels.py` — label generation (forward returns)
- Individual model dirs: `xgboost/`, `random_forest/`, `ridge/`, `lasso/`, `linear_regression/`, `lightgbm/`, `catboost/`, `elastic_net/`, `logistic_regression/`

### 8.2 RL Training Environment (Reinforcement Learning)

**Location:** `vinu-simulator/engine/simulator.py:295-457` (SimulatorEnv class)

**Gym-Compatible Interface:**
- `reset(seed)` → returns initial state vector [current_weights, cash_weight, prices]
- `step(target_weights)` → executes rebalance, returns (next_state, reward, done, info)
- Reward signal = portfolio return per step
- Properties: `equity_curve`, `daily_returns`, `metrics()`

**How It Works:**
The `SimulatorEnv` wraps `WeightSimulator` as a Gym-compatible environment. An RL agent (PPO, A2C, DQN, etc.) calls `reset()` to get initial state, `step(weights)` to execute a rebalance, and receives `(next_state, reward, done, info)`. The agent learns which weight allocations maximize cumulative reward while paying realistic transaction costs (Almgren-Chriss model).

**State Space:** [current_weights (N), cash_weight (1), prices (N)]
**Action Space:** Target portfolio weights
**Cost Integration:** Uses same cost models as classical backtesting (FlatCost, AlmgrenChriss)

### 8.3 Deflated Sharpe Ratio (Multiple Testing Correction)

**Location:** `vinu-research/walk_forward.py:124-166`

**Purpose:** Answers "Is my Sharpe real, or did I just get lucky by testing 50 strategies?"

**Inputs:**
- Observed Sharpe ratio
- Number of independent trials (strategies tested)
- Number of observations
- Skewness
- Excess kurtosis

**Output:** Probability [0,1] that observed Sharpe reflects genuine skill

**Thresholds:**
- > 0.95 = genuine skill
- 0.50-0.95 = uncertain
- < 0.50 = likely luck

**Formula (Bailey & Lopez de Prado 2014):**
Uses expected maximum Sharpe formula from order statistics of Gaussian variables to adjust for multiple testing bias.

### 8.4 Event Study Methodology (Abnormal Return)

**Location:** `vinu-correlation/engine/event_study.py`

**Components:**
- **Estimation window:** 7 days before event — establishes expected return
- **Event window:** 30 minutes after event — measures actual return
- **Expected return:** Mean return during estimation window
- **Abnormal return:** Actual return minus expected return
- **CAR:** Cumulative abnormal return over entire event window
- **t-test:** One-sample t-test for statistical significance
- **Significance classification:**
  - highly_significant (p < 0.01)
  - significant (p < 0.05)
  - marginally_significant (p < 0.10)
  - insignificant (p >= 0.10)

### 8.5 Scheduled/Cron Research Execution

**Location:** `vinu-research/scheduled/` (cron.py, executor.py, store.py, models.py)

**Components:**
- **Cron parser:** Full 5-field cron expression syntax (minute hour day month weekday)
- **Next run calculator:** Computes next execution time from cron expression
- **Task persistence:** SQLite-backed scheduled task storage
- **Auto-execution:** Background worker checks for due tasks and runs them
- **Auto-reschedule:** Tasks automatically rescheduled after completion or failure

**Use Cases:**
- Run factor decay monitoring daily
- Backtest new hypotheses weekly
- Execute research loop every weekday at 2:00 AM

### 8.6 Pairs Trading / Cointegration Analysis

**Current Status:** Exists **only as LLM swarm preset prompts** (`vinu-agent/swarm/presets/pairs_research_lab.yaml`, `statistical_arbitrage_desk.yaml`). No standalone executable module.

**Statistical Concepts (Pure Math, No LLM):**
1. **Hedge ratio:** OLS regression coefficient (β) between two price series
2. **Spread:** Residual series: spread = asset_y - β * asset_x
3. **Stationarity (ADF):** Augmented Dickey-Fuller test — is the spread mean-reverting? (p < 0.05 = yes)
4. **Cointegration (Johansen):** Johansen test — are assets cointegrated at 1% or 5% significance?
5. **Half-life:** Days until spread reverts 50% to mean (Ornstein-Uhlenbeck)
6. **Z-score:** Normalized spread: z = (spread_t - μ) / σ
7. **Entry signals:** Buy when z < -2.0, sell when z > +2.0
8. **Exit signals:** Close when z returns to 0

**Implementation (No LLM Needed):**
```python
from statsmodels.regression.linear_model import OLS
from statsmodels.tsa.stattools import adfuller, coint

# 1. Hedge ratio via OLS
model = OLS(asset_y, asset_x).fit()
hedge_ratio = model.params[0]
spread = asset_y - hedge_ratio * asset_x

# 2. Stationarity test
adf_stat, adf_pvalue, _, _, _, _ = adfuller(spread)
is_stationary = adf_pvalue < 0.05

# 3. Cointegration test
coint_stat, coint_pvalue, _ = coint(asset_y, asset_x)
is_cointegrated = coint_pvalue < 0.05

# 4. Z-score signal
z_score = (spread - spread.mean()) / spread.std()
signal = "BUY" if z_score < -2.0 else "SELL" if z_score > 2.0 else "HOLD"
```

**Libraries:** `statsmodels`, `pandas`, `numpy` (all already in the project)

---

## Summary: What LLM Adds vs What Already Exists

| Capability | Without LLM | With LLM |
|------------|-------------|----------|
| Strategy idea generation | 15 templates, keyword matching | Unlimited natural language → code |
| Risk evaluation | 19 rule-based checks | + Natural language reasoning |
| News sentiment | 100+ phrase lexicon + 72 words | + LLM nuanced analysis |
| Strategy refinement | Template parameter tuning | + Code rewrite suggestions |
| Research summaries | Structured metrics + tables | + Natural language narrative |
| Report generation | Markdown templates | + Executive summary |

**Bottom line:** Without LLM, the system provides **~250+ distinct analytical dimensions** across data, strategy, backtesting, validation, attribution, decay monitoring, ML training, RL environments, and statistical testing — all operable via API, CLI, or web UI. The LLM enhances automation and natural language but does not add new analytical capabilities.
