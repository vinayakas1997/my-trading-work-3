# 01 — Core Research Flow Test Plan

## Objective

Trace and measure every step when a user asks the agent to analyze a ticker and suggest/recommend a strategy — using **only local LLM** (Ollama), no external providers. Verify the system works end-to-end end and understand how each component behaves.

---

## System Under Test

```
User: "analyze AAPL" or "suggest a strategy for MSFT"
  │
  ▼
Agent ReAct Loop (vinu-agent)
  ├── 1. LLM decides which tools to call
  ├── 2. Tool: get_stock_price (→ vinu-stock-price → DuckDB/Parquet)
  ├── 3. Tool: get_news          (→ vinu-news → SQLite + optional LLM analysis)
  ├── 4. Tool: run_research      (→ vinu-research → StrategyResearchLoop)
  │       ├── 4a. Generate strategy (3 concurrent local LLM calls)
  │       ├── 4b. Backtest (vinu-simulator)
  │       ├── 4c. Risk critic (1 local LLM call)
  │       └── 4d. Refine & repeat (up to 5 iterations)
  ├── 5. Tool: get_story / get_drawdowns (→ vinu-correlation)
  ├── 6. Tool: get_features / factor_analysis (→ vinu-features)
  └── 7. Agent compiles final response
```

---

## What We Measure

### 1. LLM Behavior (Agent ReAct Loop)

| Metric | How |
|--------|-----|
| Number of LLM calls per request | Count every `_call_llm()` invocation |
| Latency per call | Time before/after `llm.chat()` |
| Tool selection | Which tools does the LLM decide to call? In what order? |
| Prompt size (chars) | `len(str(messages))` before truncation |
| Completion size (chars) | Length of LLM's response content |
| Number of iterations | How many ReAct cycles before completion? |
| Context growth | History length across iterations |

### 2. Tool Execution

| Metric | How |
|--------|-----|
| Which tools called | Name + params of each tool |
| Execution time per tool | From submit to result |
| Result size (chars) | Length of tool result string |
| Read-only vs write ratio | Count of each |
| Errors | Any tool exceptions |

### 3. Data Accumulation

| Metric | How |
|--------|-----|
| Price data range | From/to dates, interval, rows returned |
| News articles count | How many articles fetched |
| News LLM analysis | Is news LLM analysis enabled? How many article analyses? |
| Factor data | Which factors/themes accessed |

### 4. Research Loop (StrategyResearchLoop)

| Metric | How |
|--------|-----|
| Number of iterations | How many refine cycles? |
| Strategy candidates | How many generated? How many passed validation? |
| Backtest time | Per iteration |
| Risk critic verdict | PASS / REFINE / STOP per iteration |
| Holdout validation | Sharpe degradation on holdout |
| Walk-forward results | IS vs OOS metrics |
| Final strategy code | What code was generated? |

### 5. Response Quality

| Metric | How |
|--------|-----|
| Completion status | completed / max_iterations / error |
| Final response length | Total chars |
| Response structure | Does it include strategy code? Metrics? Explanation? |

---

## Test Scenarios

### Scenario A: Simple Data Fetch
```
Query: "Show me AAPL price data from 2024-01-01 to 2024-06-01"
```
- **Exercises**: Agent ReAct, `get_stock_price` tool, vinu-stock-price
- **Expected**: 1-2 LLM calls, 1 tool call
- **Duration**: < 30s

### Scenario B: News + Price Combined
```
Query: "Get latest news and price for MSFT"
```
- **Exercises**: Agent ReAct, `get_stock_price` + `get_news`, vinu-news query
- **Expected**: 2-3 LLM calls, 2 tool calls
- **Duration**: < 60s

### Scenario C: Strategy Research (Core)
```
Query: "Suggest a momentum strategy for SPY"
```
- **Exercises**: Full research pipeline
- **Expected**: 5+ iterations, research loop with LLM gen + backtest + risk critic
- **Duration**: 5-20 minutes (dependent on local LLM speed)

### Scenario D: Full Analysis
```
Query: "Analyze AAPL and recommend an improved strategy"
```
- **Exercises**: All tools combined, full end-to-end
- **Expected**: Multiple tool calls, research loop, factor analysis
- **Duration**: 10-30 minutes

---

## Test Harness

### Approach
A standalone Python script `testing-plans/harness/run_eval.py` that:

1. Checks all services are running (health endpoints)
2. Sends query via CLI or `httpx` to `vinu-agent`
3. Registers event hooks via `SessionService.event_bus` to capture:
   - `llm.call` — before LLM, logs iteration + prompt size
   - `llm.response` — after LLM, logs timing + response size
   - `tools.executed` — after batch tool execution
   - `loop.completed` — final result
4. Polls for result (or waits on SSE stream)
5. Saves full trace as JSON

### Output
```
testing-plans/results/
├── {scenario}_{timestamp}/
│   ├── trace.json        # Full event log with timestamps
│   ├── summary.json      # Aggregated metrics
│   ├── agent_history.json # Full message history
│   └── research_report.md # If research loop ran
└── comparison_table.md   # Updated after each run
```

### Dependencies
- `httpx` for HTTP calls to services
- `docker` or `docker-compose` to ensure services are up
- Local Ollama running with chosen model

---

## Prerequisites

| Requirement | Check |
|------------|-------|
| Ollama running | `ollama list` shows model loaded |
| Services running | `docker ps` shows all 8 services healthy |
| Market data available | Parquet files exist for SPY/AAPL/MSFT |
| News data ingested | SQLite DB has articles |
| vinu-agent API accessible | `curl localhost:8086/health` returns 200 |

---

## Success Criteria

| Criterion | Target |
|-----------|--------|
| Agent completes without crash | 100% of runs |
| Research loop generates valid strategy code | ≥ 1 candidate per run |
| Backtest executes without error | 100% of iterations |
| Risk critic returns verdict | Every iteration |
| Final response includes metrics & code | User sees actionable output |
| All tool calls succeed | No tool exceptions |

---

## What We Will Build

| Item | File | Purpose |
|------|------|---------|
| Test harness | `testing-plans/harness/run_eval.py` | Orchestrates test runs, captures events, saves results |
| Analysis notebook | `testing-plans/harness/analyze_results.py` | Reads saved results, produces comparison tables |
| Runner script | `testing-plans/run.sh` | One-command: start services → run tests → generate report |

---

## Notes

- All LLM calls are **local Ollama only** — no external API calls
- Token tracking is **character-based estimation** (Phase 3 will add real token counting)
- This plan covers **Phase 1 only** — broker/order testing and optimization are separate phases
