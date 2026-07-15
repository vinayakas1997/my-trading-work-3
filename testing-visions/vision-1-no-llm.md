# Vision 1 — Without LLM

When there is no LLM agent, the user interacts **directly** with the microservices via web UI or raw REST API. There is no autonomous orchestration, no natural language, no narrative synthesis. The user must manually chain requests, read JSON responses, and interpret results themselves.

---

## Step-by-Step Flow

### Step 1: User Decides What to Do

The user cannot speak naturally. They must understand the system architecture and manually plan their workflow:

```
I need to check MSFT.

Plan:
1. Open Strategy Dashboard at http://localhost:8084/ui/
2. Or hit each API manually via curl/HTTPie
3. First get stock price from stock-api
4. Then check news from news-api
5. Then run correlation from correlation-api
6. Then run features with ML from features-api
7. Then evaluate strategy from strategy-api
8. Piece together the analysis myself
```

---

### Step 2: User Interacts via Web UI or Raw API

#### Option A: Web UI (React Dashboards)

The user opens their browser to each service's UI:

**Strategy Dashboard** (`http://localhost:8084/ui/`)

```
┌──────────────────────────────────────────────────────────────┐
│  ☰ Strategies    MSFT ▼    [Evaluate Now]                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─ Strategies ───────────────────────────────┐              │
│  │ ○ ma_crossover                              │              │
│  │ ○ rsi_mean_reversion                        │              │
│  │ ● news_aware_momentum          ◄ selected   │              │
│  └──────────────────────────────────────────────┘              │
│                                                              │
│  ┌─ Evaluate ───────────────────────────────────┐              │
│  │  Symbol:   [MSFT__________________]          │              │
│  │  Strategy: news_aware_momentum                │              │
│  │                                             │              │
│  │  [Run Evaluation]                           │              │
│  └──────────────────────────────────────────────┘              │
│                                                              │
│  ⚠ You must also go to:                                      │
│  • features-api (port 8082) → compute MOM_20, ADX_14 first   │
│  • correlation-api (port 8083) → compute impact, granger     │
│  • The strategy needs these signals to produce weights        │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

The dashboard shows a dropdown to select strategy, a ticker input, and an Evaluate button. But the user sees a **warning banner** — the strategy requires features and correlation data that must be pre-computed separately.

The user must open **4 separate tabs**:

| Tab | URL | Action |
|-----|-----|--------|
| Stock Price | `http://localhost:8081/ui/` | View MSFT price chart, note current price |
| Features | `http://localhost:8082/ui/` | Submit request for MOM_20 + ADX_14 on MSFT |
| News + Correlation | `http://localhost:8083/ui/` | Run correlation analysis for MSFT |
| Strategy | `http://localhost:8084/ui/` | Evaluate strategy after above are done |

#### Option B: REST API (curl / HTTPie)

The user opens 4 terminal windows and runs requests manually:

**Terminal 1 — Get Stock Price:**

```bash
curl -s http://localhost:8081/candles/MSFT?interval=1d\&days=60 | jq
```

```json
{
  "symbol": "MSFT",
  "candles": [
    {"bar_ts": "2026-05-16T00:00:00", "open": 445.10, "high": 448.30, 
     "low": 443.80, "close": 447.20, "volume": 22000000},
    ...
    {"bar_ts": "2026-07-15T00:00:00", "open": 445.00, "high": 452.10, 
     "low": 444.50, "close": 450.20, "volume": 28500000}
  ],
  "current_price": 450.20,
  "change_1d_pct": 1.2
}
```

The user reads this raw JSON and notes the current price mentally.

**Terminal 2 — Compute Features + ML:**

```bash
curl -s -X POST http://localhost:8082/requests \
  -H "Content-Type: application/json" \
  -d '{
    "title": "MSFT alpha158 XGBoost",
    "symbols": ["MSFT"],
    "preset": "alpha158",
    "ml_model": "xgboost",
    "ml_label": "forward_return_1",
    "days": 500,
    "interval": "1d",
    "run_immediately": true
  }' | jq
```

```json
{
  "id": 42,
  "status": "done",
  "ml_model": "xgboost",
  "ml_label": "forward_return_1",
  "file_path": "/data/features/runs/run_42/"
}
```

The user then fetches the results:

```bash
curl -s http://localhost:8082/requests/42 | jq
```

```json
{
  "id": 42,
  "status": "done",
  "ml_model": "xgboost",
  "ml_label": "forward_return_1",
  "oos_metrics": {
    "oos_ic": 0.047,
    "train_count": 400,
    "test_count": 100
  }
}
```

The user sees `oos_ic: 0.047` and must know that this is a Spearman rank correlation — positive but modest. They need domain knowledge to interpret that this is in the top decile of ML signals.

To get MOM_20 and ADX_14 specifically (needed by the strategy):

```bash
# Can't get individual indicators from existing run; must submit a separate request
curl -s -X POST http://localhost:8082/requests \
  -H "Content-Type: application/json" \
  -d '{
    "title": "MSFT MOM ADX",
    "symbols": ["MSFT"],
    "features": ["momentum_n:period=20", "adx:period=14"],
    "days": 60,
    "run_immediately": true
  }' | jq
```

```json
{
  "id": 43,
  "status": "done",
  "file_path": "/data/features/runs/run_43/"
}
```

Then read the Parquet file:

```bash
python3 -c "
import pandas as pd
df = pd.read_parquet('/data/features/runs/run_43/features.parquet')
print(df[['ts','MOM_20','ADX_14']].tail(5))
"
```

```
          ts  MOM_20  ADX_14
495 2026-07-09    7.2    31.0
496 2026-07-10    7.8    31.5
497 2026-07-11    8.1    31.8
498 2026-07-14    8.3    32.1
499 2026-07-15    8.5    32.4
```

The user notes: "MOM_20 = 8.5, ADX_14 = 32.4 ✅"

**Terminal 3 — Get News + Correlation:**

```bash
# First check news
curl -s "http://localhost:8080/news/MSFT?days=7" | jq '.articles[] | 
  {headline, sentiment, sentiment_score, impact, price_reaction_1h}'
```

```json
{
  "headline": "Azure Cloud Revenue Surges 30%, Beats Estimates",
  "sentiment": "BULLISH",
  "sentiment_score": 5,
  "impact": "high_bullish",
  "price_reaction_1h": 2.1
}
{
  "headline": "MSFT Faces EU Antitrust Probe Over Teams Bundling",
  "sentiment": "BEARISH",
  "sentiment_score": -3,
  "impact": "medium_bearish",
  "price_reaction_1h": -0.8
}
...
```

The user manually counts: "4 bullish, 1 bearish, 8 neutral. Net = +14."

```bash
# Then run correlation analysis
curl -s "http://localhost:8083/correlation/MSFT?days=30" | jq
```

```json
{
  "correlation_news_return": {
    "r": 0.31,
    "ci_95": [0.12, 0.48],
    "significant": true
  },
  "correlation_sentiment_return": {
    "r": 0.42,
    "ci_95": [0.22, 0.57],
    "significant": true
  },
  "granger": {
    "best_lag_hours": 2,
    "p_value": 0.023,
    "causes_prices": true
  },
  "drawdown": {
    "total_drawdowns": 3,
    "news_attributed_pct": 62.0
  },
  "impact_summary": {
    "high_bullish": 4,
    "high_bearish": 1,
    "medium": 8,
    "low": 22
  },
  "baseline": {
    "z_score": 2.3,
    "level": "elevated"
  }
}
```

The user must now **mentally evaluate**: "r = 0.42 for sentiment vs returns, Granger p = 0.023 — significant. So news does correlate. 4 high-bullish events."

**Terminal 4 — Run Strategy:**

```bash
curl -s "http://localhost:8084/strategies/news_aware_momentum/evaluate?symbols=MSFT" | jq
```

```json
{
  "strategy_name": "news_aware_momentum",
  "weights": [
    {
      "symbol": "MSFT",
      "weight": 0.25,
      "direction": "long"
    }
  ],
  "rules_fired": ["news_bullish_boost"],
  "rule_effects": [
    {
      "rule": "news_bullish_boost",
      "effect": "weight 0.25 → 0.30 (capped by risk)"
    }
  ],
  "features": {
    "MOM_20": 8.5,
    "ADX_14": 32.4
  },
  "correlation": {
    "bullish_events": 4,
    "bearish_events": 1,
    "granger_significant": true
  }
}
```

The user reads this: "Weight = 0.25 long. Rules fired: news_bullish_boost. The boost tried to make it 0.30 but risk cap stopped it."

---

### Step 3: User Synthesizes Their Own Report

Without the LLM, there is **no narrative, no automatic report generation**. The user must:
1. Gather all 4 terminal outputs
2. Mentally cross-reference the data
3. Write their own analysis notes
4. Make their own trading decision

The user might open a text editor and create notes:

```
--- MSFT Analysis Notes ---
Date: 2026-07-15

Price: $450.20 (+1.2%)

News: 
- 4 bullish, 1 bearish, 8 neutral. Net sentiment = +14
- Azure earnings beat (+2.1% impact)
- EU antitrust probe (-0.8% impact)
- OpenAI partnership (+3.2% impact)

Correlation:
- Sentiment vs returns: r=0.42 (significant, CI doesn't cross 0)
- Granger p=0.023 (news predicts price, 2h lag)
- 62% of drawdowns explained by news

ML:
- XGBoost on alpha158 → OOS IC = 0.047
- Decent predictive power

Strategy:
- news_aware_momentum → 25% long
- news_bullish_boost rule fired
- Would have been 30% but risk cap

Decision: Go long MSFT at 25%. 
The news is bullish and the correlation is statistically significant.
Risk is manageable — no drawdowns active.
```

---

## What the User Sees (Without LLM)

### The Web UI Dashboard

After running evaluation on the strategy dashboard (`http://localhost:8084/ui/`):

```
┌──────────────────────────────────────────────────────────────┐
│  ☰ Strategies    MSFT    [Evaluate Now]  last run: 14:30     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─ Overview ──┬── Pipeline ──┬── Weights ──┬── Runs ──────┐│
│  │                                                         ││
│  │  Strategy: news_aware_momentum                           ││
│  │  Symbol:   MSFT                                         ││
│  │                                                         ││
│  │  ┌───────┬──────┬──────────┬────────┐                  ││
│  │  │ Step  │ Pass │  Detail  │ Value  │                  ││
│  │  ├───────┼──────┼──────────┼────────┤                  ││
│  │  │SELECT │  ✅  │ MOM_20   │ +8.5%  │                  ││
│  │  │ALLOC  │  ✅  │ base wt  │ 0.25   │                  ││
│  │  │TIMING │  ✅  │ bull_boost │ fired │                  ││
│  │  │TIMING │  ❌  │ bear_cautn│ 1<2   │                  ││
│  │  │TIMING │  ❌  │ dd_cash  │ 0<1   │                  ││
│  │  │RISK   │  ✅  │ weight   │ 0.25  │                  ││
│  │  └───────┴──────┴──────────┴────────┘                  ││
│  │                                                         ││
│  │  FINAL WEIGHT: MSFT 0.25 LONG                           ││
│  │                                                         ││
│  │  ⚠ Note: Correlation data was fetched from API.         ││
│  │    Verify news impact data at: /correlation/MSFT        ││
│  │                                                         ││
│  └─────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

The user gets a **table of pipeline results** — which stages passed, which rules fired, the final weight. There's a note telling them to go verify correlation data separately. No narrative, no synthesis, no recommendation context.

### The Raw API Responses (if using terminal)

The user sees 4 separate JSON blobs in 4 terminal windows and must correlate them manually:

```
Terminal 1 (Stock Price):
  MSFT @ $450.20 (+1.2%)

Terminal 2 (Features + ML):
  MOM_20=8.5, ADX_14=32.4
  XGBoost OOS IC=0.047

Terminal 3 (News + Correlation):
  4 bullish, 1 bearish   r=0.42   Granger p=0.023
  62% news-attributed    z=2.3σ elevated

Terminal 4 (Strategy):
  Weight=0.25 LONG   bull_boost fired → capped
```

---

## Key Characteristics of Non-LLM Flow

| Aspect | Without LLM |
|--------|-------------|
| **Input** | Click buttons in UI / write curl commands |
| **Orchestration** | User must manually plan tool sequence |
| **Data gathering** | Manual — open 4+ browser tabs or terminals |
| **Result interpretation** | User reads JSON, must understand every field |
| **Report format** | Raw JSON or basic pipeline table in web UI |
| **Depth** | Fixed — the UI shows what it shows, no drill-down |
| **Follow-ups** | "What if I change the weight?" → manual copy-paste |
| **Errors** | Technical HTTP errors: `500 Internal Server Error` or blank UI states |
| **Cross-validation** | User must mentally cross-reference: "Does the ML signal agree with the news?" |
| **User skill required** | High — must know REST APIs, JSON, financial metrics, strategy pipeline |

---

## Comparison Summary

| Dimension | With LLM | Without LLM |
|-----------|----------|-------------|
| **Time to result** | 30-60 seconds (one query) | 5-15 minutes (4+ manual API calls) |
| **Expertise needed** | None — plain English | High — know APIs, JSON, quant metrics |
| **Error handling** | Graceful: "News API unavailable, using cached data" | `curl: (7) Failed to connect`, user debug |
| **Depth of insight** | Cross-references all signals automatically | User must mentally connect dots |
| **Follow-up** | "Compare NVDA" → agent does it | New curl commands for each symbol |
| **Report quality** | Rich markdown with emojis, tables, narrative | Raw JSON or basic table UI |
| **Decision confidence** | High — LLM explains why signal confluences matter | Variable — depends on user's skill |
| **Multi-symbol** | "Analyze FAANG stocks" → 5× parallel | Manual: 5× the curl commands |
| **Strategy refinement** | "Optimize parameters for higher Sharpe" → research loop | Edit YAML, re-run, compare metrics manually |
| **Learning curve** | Zero — conversational | Steep — must learn the entire microservice architecture |

### The Critical Difference

> **Without LLM:** The system is a **powerful toolbox** — every component works, every API responds, every metric is computed. But the user must know exactly which tool to pick, in what order, and how to interpret the output.
>
> **With LLM:** The system becomes an **autonomous research analyst** — the same components, the same data, but the LLM orchestrates the multi-step pipeline, cross-validates signals, explains anomalies in context, and presents a decision-ready narrative with supporting evidence.

The underlying microservices do the same work in both scenarios. The difference is **who drives the orchestration and synthesis** — the human or the LLM.
