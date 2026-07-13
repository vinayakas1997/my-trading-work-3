# What to Build & What to Optimize

---

## Legend

| Marking | Meaning |
|---------|---------|
| ✅ | Already built |
| ⚠️ | Built but needs enhancement |
| ❌ | Not built yet |

---

## PART 1: What to Build (New Components)

### 1.1 vinu-research — Agentic Strategy Researcher ✅

**Priority:** HIGH — this is the core deliverable the user interacts with

| Sub-Component | What to Build | Effort |
|---|---|---|
| **AutoGen Agent Definitions** | Quant Coder Agent, Risk Critic Agent, GroupChatManager with system prompts | 1 day |
| **Tool Wrappers** | Python APIs wrapping: `vinu-simulator.simulate()`, `vinu-correlation.get_story()`, `vinu-features.get_indicators()` | 0.5 day |
| **Strategy Code Generator** | Template system that takes user's idea → generates runnable Python strategy class | 1 day |
| **Loop Orchestrator** | Iteration manager: run backtest → get critique → refine → repeat. Configurable max iterations (default 5). Stop when sharpe stops improving. | 0.5 day |
| **Research Report Generator** | Structured report: strategy description, before/after metrics, key findings, per-regime confidence | 1 day |
| **CLI Entry Point** | `vinu-research run "test SMA crossover on AAPL"` | 0.5 day |
| **Progress Streaming** | Real-time output showing each iteration, agent reasoning, tool calls | 0.5 day |
| **Total** | | **~5 days** |

**Key Design Decisions:**
- Agents call tools via Python API (not HTTP) for speed
- Each iteration is a full backtest + correlation query
- Report is output as structured JSON + rendered Markdown
- Strategy code is saved to a file for human review before any live use

---

### 1.2 vinu-agents — LLM Intelligence Layer ❌

**Priority:** MEDIUM — optional for basic flow, needed for rich narrative

| Sub-Component | What to Build | Effort |
|---|---|---|
| **LLM Integration** | Ollama/OpenAI client with configurable model, temperature, max tokens | 0.5 day |
| **Article Analyst** | Takes raw article → prompt → structured JSON output: sentiment[-1..1], confidence[0..1], risk_flags[], tickers[] | 1 day |
| **Market Digest** | Groups multiple articles by ticker → daily summary with key themes | 1 day |
| **Cache Layer** | SQLite table for LLM results keyed by article URL, TTL configurable | 0.5 day |
| **API Endpoints** | `POST /analyze` (single article), `GET /digest/{ticker}` (daily summary), `GET /story/{ticker}` (narrative) | 1 day |
| **LLM Cost Management** | Token counting, cost tracking, rate limiting, fallback to rule-based when LLM down | 0.5 day |
| **Total** | | **~4.5 days** |

**Key Design Decisions:**
- LLM results are cached — same article never analyzed twice
- System degrades gracefully: if LLM is down, agents use raw correlation facts
- Structured JSON output, not free text — strategies consume structured data

---

## PART 2: What to Enhance (Existing Components)

### 2.1 vinu-correlation — Story Block Enhancements ✅

**Priority:** HIGH — agents need structured facts to critique strategies

| Enhancement | Current State | What to Add | Effort |
|---|---|---|---|
| **Inter-event time gaps** | Not computed | `compute_time_gaps(symbol, from, to)` → array of `{gap_hours, before_event, after_event, session}` | 4 hours |
| **London session** | 08-12 UTC labeled "pre_market" | Add `london` session (07-15 UTC). Fix session classification to include London separately. | 2 hours |
| **DST/Calendar awareness** | Fixed UTC hours year-round | Add `pandas_market_calendars` integration for NYSE holidays, early closes, DST transitions | 4 hours |
| **Per-session correlation** | All hourly data pooled as one | Add `compute_correlation_by_session()` — returns separate correlation for london, pre_market, regular, after_hours | 3 hours |
| **Session transition analysis** | Not computed | Add `analyze_session_transition(pre_session, post_session, symbol, date)` — e.g., "does pre-market news predict regular-hours open?" | 3 hours |
| **Fix drawdown attribution** | Broken OLS (regresses y on \|y\|) | Replace with proper event-counting approach: for each drawdown, count high-impact events in the lookback window, compute fraction of drawdown "explained" by news | 3 hours |
| **Portfolio/multi-symbol endpoints** | Single-symbol only | Add `GET /correlation/batch?symbols=AAPL,MSFT,GOOG` | 2 hours |
| **Inter-session news gap** | Not computed | "How many hours between last pre-market news and market open?" Important for gapping analysis. | 2 hours |
| **Total** | | | **~3 days** |

**Desired Story Block Output Format (New):**

```json
{
  "ticker": "AAPL",
  "period": {"from": "2025-01-01", "to": "2025-12-31"},
  "impact_events": [
    {
      "date": "2025-03-15T14:30:00Z",
      "headline": "Apple downgraded by Morgan Stanley",
      "session": "regular",
      "price_change_30m": -2.3,
      "impact_label": "high_bearish",
      "time_since_last_event_hours": 72.5,
      "abnormal_return": -1.8,
      "ar_significant": true
    }
  ],
  "correlations": {
    "overall": {"pearson": -0.32, "p_value": 0.001, "sample_hours": 1872},
    "by_session": {
      "london": {"pearson": -0.41, "sample_hours": 450},
      "ny_regular": {"pearson": -0.18, "sample_hours": 890},
      "after_hours": {"pearson": -0.05, "sample_hours": 532}
    }
  },
  "session_transitions": {
    "premarket_to_open": {"avg_gap_pct": 0.8, "news_correlation": 0.42}
  },
  "drawdown_events": [
    {
      "peak_date": "2025-08-01",
      "trough_date": "2025-08-15",
      "drop_pct": -12.3,
      "news_attributed_pct": 0.65,
      "high_impact_events_in_window": 4,
      "sessions_involved": ["london", "ny_regular"]
    }
  ],
  "baseline_anomalies": [
    {"date": "2025-06-10", "z_score": 3.8, "deviation": "high", "session": "london"}
  ]
}
```

---

### 2.2 vinu-features — On-Demand Indicator API ✅

**Priority:** MEDIUM — needed for agent to request indicators mid-loop

| Enhancement | Current State | What to Add | Effort |
|---|---|---|---|
| **On-demand indicator computation** | Batch-only (submit request → wait for worker) | Add sync endpoint: `GET /indicators/{ticker}?kinds=sma_20,rsi_14,adx_14` returns values immediately | 4 hours |
| **Lightweight Python API** | HTTP-only from agent perspective | Add `get_indicator_values(symbol, kinds, from_ts, to_ts)` returning DataFrame | 2 hours |
| **Caching** | No cache for on-demand queries | Add TTL cache (60s) for indicator values | 1 hour |
| **Total** | | | **~0.5 day** |

---

### 2.3 vinu-simulator — Custom Strategy API ✅

**Priority:** HIGH — agent needs to feed custom code, not just YAML strategy names

| Enhancement | Current State | What to Add | Effort |
|---|---|---|---|
| **Custom strategy evaluation** | Only evaluates named strategies via vinu-strategy HTTP | Add `simulate_custom(weight_generator_func, symbols, dates, config)` — accepts a Python function that returns weights DataFrame | 4 hours |
| **Strategy code template** | No template | Add `BaseStrategy` class with `generate_weights(data) → DataFrame` contract | 2 hours |
| **Total** | | | **~0.5 day** |

---

## PART 3: Code Optimizations & Refactors

### 3.1 Consolidate Shared Code into vinu_lib ✅

**Problem:** HTTP clients, SQLite patterns, Parquet I/O, FastAPI boilerplate duplicated across all 6 services.

| Optimization | Current State | Target State | Effort |
|---|---|---|---|
| **Shared HTTP Client** | Each service has its own httpx client with retry/timeout/thread-safety | `vinu_lib.client.ResilientClient` — single implementation with circuit breaker, retry, fallback, OpenTelemetry | 1 day |
| **Shared SQLite Backend Base** | Each service copy-pastes `threading.local()` + WAL + migration pattern | `vinu_lib.sqlite.BaseBackend` — base class with connection pool, WAL, migration, thread safety | 1 day |
| **Shared Parquet Utilities** | Each service has own partition/append/compact logic | `vinu_lib.parquet.ParquetStore` — base class with partition helpers, append, dedup, compact | 1 day |
| **Shared FastAPI Factory** | App factory + CORS + error handlers duplicated | `vinu_lib.server.create_app()` — standard factory with health endpoint, CORS, error handlers, middleware | 0.5 day |
| **Shared Config Pattern** | Each service has own env-to-dataclass mapping | `vinu_lib.config.from_env()` — standard pattern | 0.5 day |
| **Total** | | | **~4 days** |

### 3.2 Circuit Breaker + Fallback Pattern ✅

**Problem:** One service failure cascades through the entire pipeline.

| Component | Fallback When Down |
|---|---|
| vinu-strategy → vinu-features | Use built-in SMA from stock-price query engine |
| vinu-strategy → vinu-correlation | Skip correlation stage, run on price-only |
| vinu-correlation → vinu-news | Return empty impact (cache last known data) |
| vinu-simulator → vinu-strategy | Use equal-weight portfolio as baseline |
| vinu-research → any tool | Log warning, skip refinement, continue with best-so-far |

**Implementation:** Add to `vinu_lib.client.ResilientClient`:
- Circuit breaker (3 failures → open for 30s)
- Exponential backoff retry (1s, 2s, 4s)
- Graceful fallback value per endpoint
- Health check polling (every 30s, parallel)

### 3.3 Error Handling & Logging ⚠️

| Optimization | Current State | Target State |
|---|---|---|
| Structured logging | Mixed: print, logging.WARNING, no correlation IDs | JSON structured logs with request_id, component, duration |
| Trace IDs | Not implemented | OpenTelemetry or simple UUID header propagated across services |
| Graceful degradation | Crash on first error | Circuit breaker + fallback + clear error messages |

### 3.4 Testing Gaps ⚠️

| Area | Current Coverage | Target |
|---|---|---|
| vinu-strategy | 64 tests | Good baseline |
| vinu-correlation | Limited | Add tests for: story block output, per-session correlation, time gaps |
| vinu-simulator | Present | Add tests for custom strategy evaluation |
| vinu-features | Present | Add tests for on-demand indicator API |
| Integration tests | None | Add end-to-end tests: "run full pipeline for AAPL, verify output" |
| vinu-research | None (not built) | Test: "given a strategy idea, does the loop produce a better strategy?" |

---

## PART 4: Implementation Order

### Phase 1 — Foundation (2 weeks)
| Step | Component | What | Depends On |
|---|---|---|---|
| 1 | vinu-correlation | Add story blocks: time gaps, London session, per-session correlation, DST calendar, fix drawdown | — |
| 2 | vinu-lib | Build shared HTTP client with circuit breaker + fallback | — |
| 3 | vinu-features | Add on-demand indicator API, lightweight Python wrapper | Step 1 |
| 4 | vinu-simulator | Add custom strategy evaluation, BaseStrategy template | — |

### Phase 2 — Agent Loop (1 week)
| Step | Component | What | Depends On |
|---|---|---|---|
| 5 | vinu-research | Build AutoGen agents + tool wrappers + loop orchestrator | Phase 1 |
| 6 | vinu-research | Build report generator + CLI | Step 5 |
| 7 | Integration | Test end-to-end: "test SMA20/SMA50 on AAPL" → research report | Step 6 |

### Phase 3 — Narrative Layer (1 week optional)
| Step | Component | What | Depends On |
|---|---|---|---|
| 8 | vinu-agents | Build LLM integration + article analyst + market digest | — |
| 9 | vinu-agents | Wire into vinu-research as optional narrative enhancer | Step 8 |
| 10 | Integration | Full test: with and without LLM, compare outputs | Step 9 |

### Phase 4 — Production Hardening (ongoing)
| Step | What | When |
|---|---|---|
| 11 | Consolidate vinu_lib (SQLite, Parquet, FastAPI base classes) | As-needed during refactors |
| 12 | Add structured logging + trace IDs | Before first external use |
| 13 | Add integration tests | After each phase |
| 14 | Add monitoring/alerting | Before live use |

---

## PART 5: Story Is the Main — What to Build (Step by Step with User Experience)

### Step 1: Enhance vinu-correlation "Story Blocks" (2 days)

**This is the foundation.** The agents need structured facts, not raw stats.

| Missing Block | What to Add | Why the Agent Needs It |
|---|---|---|
| **Inter-event time gaps** | `compute_time_gaps(symbol)` → returns `[{gap_hours, before_event, after_event, session}]` | Agent asks: "was this drawdown from a single big event or multiple rapid events?" |
| **London session** | Add `london` session (07-15 UTC) | Agent asks: "was this during London open volatility or US regular hours?" |
| **Per-session correlation** | Breakdown correlation by session (London, NY pre, NY regular, after-hours) | Agent asks: "does news impact differ between London and NY sessions?" |
| **Session transition** | Pre-market → regular open gap analysis | Agent asks: "did pre-market news predict the open gap?" |
| **Fix drawdown attribution** | Replace broken OLS model with event-counting approach | Currently mathematically invalid |
| **Story block output** | New structured JSON format: `{"ticker","date","events":[{"impact_pct","session","time_since_last","bearish/bullish"}],"correlations":{...}}` | This is what the Risk Critic Agent consumes directly |

---

### Step 2: Build vinu-agents — LLM Layer on News (2-3 days)

Optional for basic flow but adds the "narrative" layer on top of the story facts.

| Module | What It Does |
|---|---|
| **Article Analyst** | Takes article → LLM → structured sentiment, ticker relevance, confidence |
| **Market Digest** | Summarizes multiple articles into ticker-level daily narrative |
| **Cache Layer** | Stores LLM results so same article isn't re-analyzed |
| **API** | `POST /analyze`, `GET /digest/{ticker}`, `GET /story/{ticker}` |

---

### Step 3: Build vinu-research — The AutoGen Loop (4-5 days)

**This is the main piece.** The multi-agent system that takes "test SMA20/SMA50 crossover" and outputs a research report.

| Component | What It Does |
|---|---|
| **Quant Coder Agent** | Writes strategy → calls vinu-features for indicators → calls vinu-simulator → gets PnL |
| **Risk Critic Agent** | Reads PnL → queries vinu-correlation story blocks → critiques: "this drawdown was from London session news spikes" |
| **GroupChat Manager** | Loops Coder ↔ Critic until strategy is optimized or max iterations reached |
| **Tool Wrappers** | Clean Python APIs for: `run_backtest(strategy_code, ticker, dates)`, `get_correlation_story(ticker, dates)`, `get_features(ticker, indicators)` |
| **Report Generator** | Outputs: "SMA20/SMA50 on AAPL: Sharpe X → Y after refinement. Best conditions: NY regular hours only, add ADX filter. Avoid trading 2h after high-impact news." |
| **CLI / API** | `vinu-research run "test sma50 crossover on AAPL for 2025"` |

---

### Step 4: Integration & Polish (2 days)

- Wire full end-to-end flow
- Add iteration limits (stop after 5 refinements or sharpe stops improving)
- Add human-in-the-loop checkpoint after final output
- Add progress streaming so you see the reasoning in real time

---

### What the User Experience Looks Like When Done

```
$ vinu-research run "test sma20/sma50 crossover on AAPL 2025"

[vinu-research] Starting strategy research for: SMA20/SMA50 crossover on AAPL
[Iteration 1/5]
  Quant Coder: Created basic SMA crossover strategy
  Simulator: Sharpe=0.72, MaxDD=-18.3%, WinRate=51%
  Risk Critic: Checking vinu-correlation stories...
    → 3 major drawdowns during London session (high news volatility)
    → 2 drawdowns within 2 hours of bearish news events
    → Gap between news events: avg 4.2 hours on bad days
  Risk Critic: SUGGESTION - Add ADX filter + avoid London session
               + skip trading 1h after high-impact news

[Iteration 2/5]
  Quant Coder: Added ADX>20 filter, London session skip,
               news cooling-off period
  Simulator: Sharpe=1.12, MaxDD=-9.8%, WinRate=56%
  Risk Critic: Improved, but still 2 drawdowns during earnings week...

[Iteration 5/5]
  Simulator: Sharpe=1.35, MaxDD=-6.2%, WinRate=61%
  ✓ Strategy stabilized. No further improvement.

=== FINAL RESEARCH REPORT ===
Strategy: SMA20/SMA50 Crossover (refined)
Ticker: AAPL
Time Period: 2025

Refinements Applied:
  1. ADX filter (>20) - avoids choppy sideways markets
  2. London session exclusion (07:00-13:00 UTC) - high news volatility
  3. News cooling-off period (skip 60min after impact>medium)
  4. Earnings week position sizing (-50%)

Final Metrics:
  Sharpe: 1.35 (was 0.72)
  Max Drawdown: -6.2% (was -18.3%)
  Win Rate: 61% (was 51%)
  News-driven losses avoided: 4 major events

Confidence Assessment:
  NY Regular Session: HIGH (Sharpe 1.6 in this regime)
  London Session: LOW (avoid)
  Earnings Weeks: MEDIUM (reduce position size)
```

---

## Summary: What's Built vs What's Missing

| Component | Status | Phase | When |
|---|---|---|---|
| vinu-news | ✅ Built | — | Done |
| vinu-stock-price | ✅ Built | — | Done |
| vinu-features | ✅ Built | — | Done |
| vinu-correlation | ✅ Built (story blocks done) | Phase 1 | Done |
| vinu-strategy | ✅ Built | — | Done |
| vinu-simulator | ✅ Built (custom strategy eval done) | — | Done |
| vinu-lib shared | ✅ Built (6 modules + circuit breaker) | Phase 1+4 | Done |
| vinu-research | ✅ Built | Phase 2 | Done |
| vinu-agents | ❌ Not built (optional) | Phase 3 | Optional |

**Critical path:** vinu-correlation enhancements → vinu-research → end-to-end integration

Everything in Phase 1 is needed before vinu-research can consume real story blocks.
Without those story blocks, the Risk Critic Agent can only say "drawdown bad" — not "drawdown was from London session news spikes."
