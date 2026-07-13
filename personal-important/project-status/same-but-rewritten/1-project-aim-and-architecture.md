# Project Aim & Architecture

## One-Line Vision

Build an **Agentic Strategy Researcher** — an AI system that acts like a human quant researcher: you give it a strategy idea, it automatically backtests, researches why it fails (news impact, session effects, market regime), iteratively refines the strategy, and outputs an optimized version with a full research report explaining its reasoning.

---

## What It Is NOT

- This is NOT a live trading bot
- This is NOT a simple parameter optimizer
- This is NOT a single-model ML system

---

## Master Flow

```
                      USER INPUT
                          |
                          v  "Test SMA20/SMA50 crossover on AAPL"
  ┌─────────────────────────────────────────────────────────────┐
  │                    vinu-research                             │
  │  ┌──────────────┐    ┌──────────────┐                       │
  │  │ Quant Coder  │◄──►│ Risk Critic  │  (AutoGen loop)       │
  │  │   Agent      │    │   Agent      │                       │
  │  └──────┬───────┘    └──────┬───────┘                       │
  └─────────┼───────────────────┼───────────────────────────────┘
            │                   │
            v                   v
  ┌─────────────────┐  ┌─────────────────┐
  │  vinu-features  │  │ vinu-correlation │
  │  (indicators)   │  │  (story blocks)  │
  └────────┬────────┘  └────────┬─────────┘
           v                    │
  ┌─────────────────┐           │
  │ vinu-stock-price│           │
  │  (OHLCV data)   │           │
  └────────┬────────┘           │
           v                    v
  ┌─────────────────┐  ┌─────────────────┐
  │  vinu-simulator │  │   vinu-news     │
  │  (backtest)     │  │  (raw articles)  │
  └─────────────────┘  └─────────────────┘
           │
           v
  ┌───────────────────────────────────────┐
  │         FINAL OUTPUT                  │
  │  Research Report + Optimized Strategy │
  └───────────────────────────────────────┘
```

---

## Detailed Data Flow

```
Step 1: USER says "Test SMA20/SMA50 crossover on AAPL for 2025"

Step 2: vinu-research (Quant Coder Agent)
  ├── Creates strategy code (SMA crossover)
  ├── Calls vinu-features → gets SMA20, SMA50 columns for AAPL
  │     └── vinu-features fetches OHLCV from vinu-stock-price
  ├── Calls vinu-simulator → backtests the strategy
  │     └── Returns: Sharpe, MaxDD, WinRate, trade log, equity curve

Step 3: vinu-research (Risk Critic Agent)
  ├── Reads the backtest results
  ├── Calls vinu-correlation → gets "story blocks"
  │     └── Returns structured facts:
  │         ├── Impact events on drawdown days
  │         ├── Session classification (London/NY/after-hours)
  │         ├── Time gaps between consecutive news
  │         ├── Per-session correlation news vs returns
  │         └── Baseline deviation (was news volume abnormal?)
  ├── (Optional) Calls vinu-agents → LLM interprets stories as narrative
  └── Outputs critique: "Drawdowns happened during London session
      high-news-volatility days. Add ADX filter + session filter."

Step 4: LOOP (Iteration 2..N)
  ├── Quant Coder refines strategy (adds ADX, session filter)
  ├── Risk Critic re-evaluates
  └── Stop when: sharpe stops improving OR max iterations reached

Step 5: FINAL OUTPUT
  ├── Research Report (human-readable)
  │   ├── Strategy description and refinements applied
  │   ├── Before/After metrics table
  │   ├── Key findings (session effects, news dependencies)
  │   └── Confidence assessment per market regime
  └── Optimized Strategy Code (ready for human review)
```

---

## Component Responsibilities

### vinu-news (Port 8080)
**Role:** Raw news ingestion and analysis
- RSS feed polling and parsing
- Article enrichment (NER, ticker extraction, dedup)
- Story thread clustering
- LLM analysis (optional, on-demand)
- Price reaction tagging
- Provides: structured articles with sentiment, impact, tickers

### vinu-stock-price (Port 8081)
**Role:** Market data backbone
- OHLCV 1m candle storage (Parquet archive)
- Live ingest via provider polling
- Symbol catalog and watchlist management
- Query engine with indicator computation
- Provides: clean price data for all downstream services

### vinu-features (Port 8082)
**Role:** Technical indicator engine
- 27 technical indicators (SMA, EMA, RSI, MACD, ADX, etc.)
- 11 preset recipes (basic_ta, alpha158, alpha360, etc.)
- ML model scoring (LightGBM, Random Forest, Ridge, Lasso)
- Batch feature request processing with worker
- Provides: numeric feature matrices for strategies

### vinu-correlation (Port 8083)
**Role:** News-price story builder (the "stepping blocks")
- Per-article price impact (5m/15m/30m/1h/1d windows)
- Inter-event time gap computation
- Session-aware analysis (London, NY pre-market, NY regular, after-hours)
- Session transition analysis (pre-market → regular open)
- Hourly Pearson correlation with bootstrap CI
- Granger causality test (news → prices)
- Abnormal return / CAR computation (event study)
- Drawdown detection with news attribution
- News volume baseline with Z-score anomaly detection
- **Provides:** Structured story blocks that agents consume

### vinu-strategy (Port 8084)
**Role:** Decision fusion engine
- 4-stage pipeline: Selection → Allocation → Timing → Risk
- YAML-defined strategies (AI-authorable)
- Rule DSL with safe expression evaluator
- Scheduler for automated evaluation
- Weight signal output for simulator/execution
- **Note:** Hosts the FINAL strategy after vinu-research optimizes it

### vinu-simulator (Port 8085)
**Role:** Backtest engine with realistic costs
- Daily rebalance simulation
- Flat and Almgren-Chriss cost models (slippage + market impact)
- 10 performance metrics (Sharpe, Sortino, MaxDD, Calmar, etc.)
- Benchmark comparison (SPY, QQQ, or custom)
- Trade log with per-trade costs
- RL environment (Gymnasium-style)
- **Provides:** Realistic backtest results for agents to evaluate

### vinu-agents (Not Built)
**Role:** LLM intelligence layer on news
- Chain-of-thought article analysis
- Structured sentiment/confidence/risk output
- Ticker-level market digest / daily summary
- LLM cost management and caching
- **Provides:** LLM-enhanced narrative on top of correlation story blocks
- **Optional:** The system works without this (uses raw story blocks)

### vinu-research (Built)
**Role:** Agentic Strategy Researcher (the brain)
- AutoGen multi-agent loop: Quant Coder + Risk Critic + GroupChatManager
- Takes user's strategy idea → iteratively refines → outputs report
- Tool wrappers for simulator, correlation, features
- Strategy code generator/template system
- Research report generator (before/after metrics, findings, confidence)
- **This is the final layer that produces the output the user sees**

---

## Architecture Layers Summary

```
Layer 5: AGENTIC RESEARCH     vinu-research (AutoGen loop)
──────────────────────────────────────────────────
Layer 4: LLM NARRATIVE       vinu-agents (optional)
──────────────────────────────────────────────────
Layer 3: INTELLIGENCE         vinu-correlation (stories)
                              vinu-features (indicators)
──────────────────────────────────────────────────
Layer 2: DATA PILLARS         vinu-news (text)
                              vinu-stock-price (prices)
──────────────────────────────────────────────────
Layer 1: BACKTEST & OUTPUT    vinu-simulator (backtest)
                              vinu-strategy (final strategy)
```

The system works bottom-up. Each layer feeds the one above.
vinu-research orchestrates everything and is the only layer the user interacts with directly.
