# Vision 1 — With LLM

When the LLM agent is running, the entire pipeline becomes a **conversational autonomous research analyst**. The user speaks in plain English, the agent reasons, calls tools, crunches data, and returns a structured narrative report.

---

## Step-by-Step Flow

### Step 1: User Speaks

```
User: "Check MSFT for me. How does the news look, 
       does the sentiment actually correlate with price moves, 
       run the ML model on alpha158 features, 
       and tell me what the news-aware strategy recommends."
```

### Step 2: LLM Receives the Query

The agent loads:
- **System prompt** — its role as a quantitative trading analyst
- **Skill documents** (20 skills) → technical-basic, strategy-generate, sentiment-analysis, risk-analysis, report-generate, etc.
- **Tool definitions** (17 tools in OpenAI function-calling format)
- **Session memory** — previous conversations, saved facts

### Step 3: LLM Plans the Pipeline

The LLM **reasons internally** (this is not shown to the user, but it chooses the sequence):

```
Query breakdown:
1. "Check MSFT" → get_stock_price for current price + recent performance
2. "How does the news look" → get_news for MSFT with enriched sentiment
3. "Does sentiment correlate with price" → get_correlation for MSFT
4. "Run ML model on alpha158" → get_features with preset=alpha158, ml_model=xgboost
5. "News-aware strategy" → run_strategy with news_aware_momentum
6. Synthesize everything into a report
```

### Step 4: Tool Calls Execute (LLM Orchestrates)

The LLM makes **sequential tool calls**, each one invoking a microservice:

#### Tool 1: `get_stock_price`

```
LLM calls: get_stock_price(symbol="MSFT", interval="1d", days=60)

           └─► vinu-stock-price API (port 8081)
                 ├── DuckDB reads Parquet files for MSFT
                 ├── Returns 60 daily OHLCV candles
                 └── Response: {current_price: 450.20, change_1d: +1.2%, 
                                 high_60d: 455.00, low_60d: 420.10, ...}
```

#### Tool 2: `get_news`

```
LLM calls: get_news(symbol="MSFT", days=7)

           └─► vinu-news API (port 8080)
                 ├── Queries SQLite enriched articles for MSFT
                 ├── Each article has:
                 │     headline, summary, sentiment (BULLISH/BEARISH/NEUTRAL),
                 │     sentiment_score, impact (HIGH/MEDIUM/LOW), 
                 │     category, threat_level, source_credibility,
                 │     ticker_dominance, price_reaction_1h, price_reaction_1d
                 ├── Cosine dedup applied → cluster IDs
                 └── Response: [
                       {headline: "Microsoft Azure Cloud Revenue Surges 30%, 
                         Beats Estimates", sentiment: "BULLISH", 
                         sentiment_score: 5, impact: "high_bullish",
                         price_reaction_1h: +2.1%, category: "EARNINGS"},
                       {headline: "MSFT Faces EU Antitrust Probe Over Teams 
                         Bundling", sentiment: "BEARISH", 
                         sentiment_score: -3, impact: "medium_bearish",
                         price_reaction_1h: -0.8%, category: "REGULATORY"},
                       ...
                     ]
```

#### Tool 3: `get_correlation`

```
LLM calls: get_correlation(symbol="MSFT", days=30)

           └─► vinu-correlation API (port 8083)
                 │
                 ├── impact engine → per-article price changes + abnormal returns
                 ├── correlation engine → Pearson r (news count vs returns)
                 ├── correlation engine → Pearson r (sentiment vs returns)
                 ├── bootstrap CI → 95% confidence interval
                 ├── lag analysis → optimal lag = 15 min
                 ├── granger causality → lag=2h, p=0.023 → significant ✓
                 ├── drawdown analysis → 3 drawdowns, 62% news-attributed
                 ├── baseline z-scores → current = 2.3σ (elevated)
                 └── Response: {
                       correlation_news_return: {r: 0.31, ci_95: [0.12, 0.48], significant: true},
                       correlation_sentiment_return: {r: 0.42, ci_95: [0.22, 0.57], significant: true},
                       granger: {best_lag_hours: 2, p_value: 0.023, causes_prices: true},
                       drawdown: {total_drawdowns: 3, news_attributed_pct: 62.0},
                       impact_summary: {high_bullish: 4, high_bearish: 1, medium: 8, low: 22},
                       baseline: {z_score: 2.3, level: "elevated"}
                     }
```

#### Tool 4: `get_features` (with ML model)

```
LLM calls: get_features(symbol="MSFT", preset="alpha158", 
                        ml_model="xgboost", ml_label="forward_return_1", 
                        days=500, interval="1d")

           └─► vinu-features API (port 8082)
                 │
                 ├── 1. FeatureEngine fetches 500 days OHLCV from stock-api
                 ├── 2. Computes 158 alpha features (K-bar, price lags, volume lags, 
                 │         rolling ROC/MA/STD/BETA/RSQR/RESI/MAX/MIN/SUMP/SUMN/...)
                 ├── 3. run_ml_step():
                 │       ├── build_label: forward_return_1 (next day's return)
                 │       ├── X = 158 features, y = forward return
                 │       ├── Time-ordered 80/20 split (first 400 days train, last 100 test)
                 │       ├── XGBoost(n_estimators=50, max_depth=5)
                 │       │     .fit(X_train, y_train)
                 │       │     .predict(X_test) → ml_score per row
                 │       ├── OOS IC = 0.047 (Spearman rank correlation)
                 │       └── scores.parquet written
                 │
                 └── Response: {
                       symbol: "MSFT",
                       row_count: 500,
                       ml_model: "xgboost",
                       ml_label: "forward_return_1",
                       oos_metrics: {oos_ic: 0.047, train_count: 400, test_count: 100},
                       // User can also query scores.parquet for per-row ml_score
                     }
```

#### Tool 5: `run_strategy`

```
LLM calls: run_strategy(strategy_name="news_aware_momentum", 
                        symbol="MSFT", date="2026-07-15")

           └─► vinu-strategy API (port 8084)
                 │
                 ├── 1. Loads news_aware_momentum.yaml:
                 │       features_required: [MOM_20, ADX_14]
                 │       correlation_required: [impact, granger, drawdown]
                 │
                 ├── 2. Fetches MOM_20 + ADX_14 from features-api
                 │       MOM_20 = +8.5% (positive momentum)
                 │       ADX_14 = 32.4 (strong trend, >25 threshold)
                 │
                 ├── 3. Fetches correlation signals from correlation-api
                 │       high_impact_bullish_events = 4
                 │       high_impact_bearish_events = 1
                 │       granger_causes_prices = true
                 │       drawdown_count = 0
                 │
                 ├── 4. WeightPipeline.run():
                 │       ├── selection: MOM_20 >= 0 → MSFT selected ✓
                 │       ├── allocation: signal_scaled(MOM_20) → weight = 0.25
                 │       ├── timing: rules engine evaluates:
                 │       │     Rule 1: news_bullish_boost
                 │       │       WHEN: high_impact_bullish(4) > 1 ✓
                 │       │             granger_causes_prices(true) ✓
                 │       │             ADX_14(32.4) > 25 ✓
                 │       │       THEN: weight × 1.20 → 0.25 → 0.30
                 │       │     Rule 2: news_bearish_caution
                 │       │       WHEN: high_impact_bearish(1) > 2 ✗ (skipped)
                 │       │     Rule 3: drawdown_cash
                 │       │       WHEN: drawdown_count(0) > 1 ✗ (skipped)
                 │       └── risk: normalize → max_weight(0.25) cap applied
                 │                   weight capped at 0.25
                 │
                 └── Response: {
                       strategy: "news_aware_momentum",
                       symbol: "MSFT",
                       recommendation: {
                         weight: 0.25,
                         direction: "long",
                         rules_fired: ["news_bullish_boost"],
                         rule_effects: [
                           {rule: "news_bullish_boost", 
                            effect: "weight 0.25 → 0.30 (before cap)"}
                         ]
                       },
                       features: {MOM_20: 8.5, ADX_14: 32.4},
                       correlation: {bullish_events: 4, bearish_events: 1, 
                                     granger_significant: true}
                     }
```

### Step 5: LLM Synthesizes Final Report

The LLM now has data from **5 microservices**. It synthesizes everything into a cohesive narrative.

---

## What the User Sees (Agent Response)

```
───────────────────────────────────────────────────────────────────
  Vinu Agent — MSFT Analysis Report
  2026-07-15 14:30 UTC
───────────────────────────────────────────────────────────────────

📊 PRICE OVERVIEW
  Current: $450.20 (+1.2% today)
  60d High: $455.00  |  60d Low: $420.10
  MOM_20: +8.5% (positive momentum)  |  ADX_14: 32.4 (strong trend)

📰 NEWS SENTIMENT (Last 7 Days)
  ┌─────────────────────────────────────────────────────────────┐
  │  BULLISH:   4 articles  │  BEARISH: 1 article              │
  │  NEUTRAL:   8 articles  │                                  │
  │  Net Sentiment Score: +14 (overwhelmingly positive)         │
  ├─────────────────────────────────────────────────────────────┤
  │  Top Stories:                                               │
  │  ✅ Azure Cloud Revenue Surges 30%, Beats Estimates         │
  │     → Sentiment: +5 BULLISH  |  Price Impact: +2.1%       │
  │  ✅ Copilot AI Subscriptions Reach 2M Enterprise Users      │
  │     → Sentiment: +4 BULLISH  |  Price Impact: +1.5%       │
  │  ⚠️ EU Antitrust Probe Over Teams Bundling                 │
  │     → Sentiment: -3 BEARISH |  Price Impact: -0.8%        │
  │  ✅ Strategic Partnership with OpenAI Announced             │
  │     → Sentiment: +5 BULLISH  |  Price Impact: +3.2%       │
  └─────────────────────────────────────────────────────────────┘

🔗 NEWS-PRICE CORRELATION ANALYSIS
  ┌─────────────────────────────────────────────────────────────┐
  │  News count vs Returns:  r = 0.31  [95% CI: 0.12–0.48]    │
  │  Sentiment vs Returns:   r = 0.42  [95% CI: 0.22–0.57]    │
  │                                                             │
  │  Granger Causality Test: ✅ SIGNIFICANT (p=0.023)          │
  │  → News volume DOES predict MSFT price movements           │
  │  → Optimal lag: 2 hours (news → price impact)              │
  │                                                             │
  │  Drawdown Attribution: 62% of MSFT drawdowns explained     │
  │  by news events (vs 28% market beta, 10% unexplained)      │
  │                                                             │
  │  News Volume Baseline: z-score = 2.3σ (elevated)           │
  └─────────────────────────────────────────────────────────────┘

🤖 ML MODEL (XGBoost on Alpha158)
  ┌─────────────────────────────────────────────────────────────┐
  │  Model:       XGBoost (50 trees, depth 5)                  │
  │  Features:    158 alpha factors (K-bar, ROC, MA, STD,      │
  │               BETA, RSQR, RESI, CORR, SUMP, etc.)          │
  │  Label:       1-day forward return                         │
  │  Training:    400 days (80%) | Test: 100 days (20%)        │
  │                                                             │
  │  OOS Information Coefficient: 0.047                         │
  │  → Model has positive predictive power (top 20% of ML       │
  │     models in production)                                   │
  │  → Top predictive factors: BETA_30, ROC_20, SUMP_10        │
  └─────────────────────────────────────────────────────────────┘

📋 STRATEGY: News-Aware Momentum
  ┌─────────────────────────────────────────────────────────────┐
  │  Pipeline:                                                  │
  │  Step 1: Selection                                          │
  │    MOM_20 (+8.5% ≥ 0) → MSFT selected ✓                    │
  │                                                             │
  │  Step 2: Allocation                                         │
  │    signal_scaled(MOM_20) → base weight = 0.25               │
  │                                                             │
  │  Step 3: Timing Rules                                       │
  │    ✅ news_bullish_boost FIRED                               │
  │       → 4 high-bullish events (>1)                          │
  │       → Granger confirms news drives price                  │
  │       → ADX_14 = 32.4 (>25 strong trend)                    │
  │       → Effect: weight 0.25 → 0.30 (boosted 20%)           │
  │                                                             │
  │    ❌ news_bearish_caution: 1 bearish event (>2 needed)     │
  │    ❌ drawdown_cash: 0 drawdowns (>1 needed)                │
  │                                                             │
  │  Step 4: Risk Normalization                                 │
  │    max_weight cap (0.25) applied → 0.30 → 0.25              │
  │                                                             │
  │  ════════════════════════════════════════════════════════   │
  │   FINAL RECOMMENDATION: MSFT 25% LONG                       │
  │  ════════════════════════════════════════════════════════   │
  └─────────────────────────────────────────────────────────────┘

🎯 KEY INSIGHTS
  1. News sentiment is strongly bullish (net +14) and significantly
     correlated with price movements (r=0.42, Granger p=0.023)
  2. XGBoost confirms predictive signal (IC=0.047) using 158 alpha factors
  3. Strategy recommends 25% long — news_bullish_boost rule fired but
     risk cap prevented full boost
  4. Consider: increasing max_weight from 0.25 to 0.30 to allow 
     the news-alpha-confluence to express fully

───────────────────────────────────────────────────────────────────
  Options: [Run Backtest] [Deep Research] [Execute Trade] [Ask]
───────────────────────────────────────────────────────────────────
```

---

## Key Characteristics of LLM-Powered Flow

| Aspect | With LLM |
|--------|----------|
| **Input** | Natural language query ("check MSFT for me") |
| **Orchestration** | LLM autonomously decides tool sequence |
| **Data gathering** | Automatic — all 5 microservices queried |
| **Result interpretation** | LLM reads JSON, converts to narrative |
| **Report format** | Rich markdown with emojis, tables, charts |
| **Depth** | LLM decides depth — can drill down or summarize |
| **Follow-ups** | Conversational: "What if I increase max_weight?" |
| **Errors** | LLM handles gracefully: "News API is down, using cached data from 2h ago" |
| **Cross-validation** | LLM cross-references: "XGBoost says up, but news says cautious → here's why..." |
| **User skill required** | Zero — talk in plain English |
