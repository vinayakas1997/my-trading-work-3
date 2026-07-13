# 2026-07-13 — Phases Implementation Plan

## Current State Overview

| Component | Status | Port | Notes |
|-----------|--------|------|-------|
| vinu-news | ✅ Built | 8080 | RSS polling, article enrichment, story threads, LLM analysis |
| vinu-stock-price | ✅ Built | 8081 | OHLCV 1m candles, Parquet archive, live ingest, query engine |
| vinu-features | ✅ Built | 8082 | 27 technical indicators, 11 preset recipes, ML scoring, batch workers |
| vinu-correlation | ⚠️ Needs enhancements | 8083 | Core engine works, but story blocks are incomplete |
| vinu-strategy | ✅ Built | 8084 | 4-stage pipeline, YAML strategies, rule DSL, scheduler |
| vinu-simulator | ✅ Built | 8085 | Daily rebalance, cost models, 10 metrics, RL environment |
| vinu_lib | ⚠️ Barely exists | — | Only `__init__.py` and `db.py` (SQLite migration helpers). No shared HTTP client, no shared server factory |
| vinu-research | ❌ Not built | — | The main deliverable — AutoGen multi-agent loop |
| vinu-agents | ❌ Not built | — | Optional LLM narrative layer on news |

---

## Phase 0 — vinu-correlation Story Block Enhancements (~3 days)

**Priority: HIGHEST** — The Risk Critic Agent needs structured facts (story blocks), not raw stats. Without them, the agent can only say "drawdown bad" — not "drawdown was from London session news spikes."

### What's Already Implemented
- All 5 impact windows (5m, 15m, 30m, 1h, 1d) in a single pass
- Basic market hours session classification (pre/regular/after/closed)
- Session-aware impact windows (truncated at session boundaries)
- Event study methodology (abnormal returns, CAR, p-values, significance)
- Granger causality tests (news → price direction)
- Bootstrap confidence intervals on Pearson correlation
- Lag analysis (best_lag_minutes)
- Multi-factor drawdown attribution skeleton
- Session-aware baselines with z-score deviation detection
- Incremental compute with Parquet append + compaction
- TTLCache layer
- Multi-ticker handling (primary + secondary with 0.5x weight)
- Story thread aggregation
- CLI with serve/compute/compact/query commands

### Step 0a — Fix London Session Classification
**Current state:** `classify_session()` has:
- `pre_market` = 08-13 UTC
- `regular` = 13-20 UTC
- `after_hours` = 20-24 UTC
- `closed` = 0-8 UTC

**Problem:** The 08-13 UTC block is labeled "pre_market" but actually overlaps London hours (07-15 UTC). This conflates two different trading sessions.

**What to do:**
- Add `london` session = 07-15 UTC
- Add `ny_premarket` = 13-14:30 UTC (covers the overlap)
- Rename existing categories to avoid ambiguity
- Update all downstream consumers (impact window truncation, correlation, baseline)
- Update schemas, API responses, and frontend

### Step 0b — Add DST/Calendar Awareness
**Current state:** Fixed UTC hours year-round. This is wrong because:
- NYSE opens at 14:30 UTC during DST (March-November)
- NYSE opens at 14:30 UTC during standard time (November-March) — wait, it's 13:30 UTC for premarket
  - Actually: NYSE regular hours are 9:30-16:00 ET. During DST that's 13:30-20:00 UTC. During standard time that's 14:30-21:00 UTC.

**What to do:**
- Add `exchange_calendars` or `pandas_market_calendars` as a dependency
- Create `MarketCalendar` utility that knows NYSE holidays, early closes (1pm ET days), DST transitions
- Replace hardcoded UTC hour ranges with calendar-aware session boundaries
- Store session boundaries per-timestamp, not as a single function

### Step 0c — Fix Drawdown Attribution
**Current state:** `attribute_drawdown()` uses OLS regression of `price_change` on `|price_change|` (impact_scores). This is mathematically circular — you can't regress y on |y|. The function hardcodes `news_pct = 0.3` as fallback when regression fails (which is most of the time).

**What to do:**
- Replace with proper **event-counting approach**:
  1. For each drawdown period (peak → trough), scan for high-impact news events
  2. Count events with `impact_label` = "high_bearish" or "high_bullish"
  3. Compute `fraction_explained = abs(sum(price_changes_of_high_impact_events)) / total_drawdown`
  4. Remove the OLS regression entirely
- Add `sessions_involved` field (which sessions saw the high-impact events)
- Add `events_in_window` count

### Step 0d — Add Computational Blocks for Story Blocks
These are the individual computations that feed into the consolidated story block output:

| Block | Function | What It Returns |
|-------|----------|-----------------|
| Inter-event time gaps | `compute_time_gaps(symbol, from_ts, to_ts)` | Array of `{gap_hours, before_event, after_event, session}` |
| Per-session correlation | `compute_correlation_by_session(symbol, from_ts, to_ts)` | Dict of `{session_name: {pearson, p_value, sample_hours}}` |
| Session transition analysis | `analyze_session_transition(symbol, pre_session, post_session, date)` | Dict: `{avg_gap_pct, news_correlation, samples}` |
| Baseline anomalies | Already implemented | But needs to be included in story block output |

### Step 0e — Build Consolidated Story Block Endpoint
**Current state:** No single endpoint returns all structured facts. The Risk Critic Agent needs to call 4 separate endpoints (impact, correlation, drawdown, baseline) and piece them together.

**What to build:**
- `GET /story/{ticker}?from=...&to=...` returning a single JSON structure:

```json
{
  "ticker": "AAPL",
  "period": {"from": "...", "to": "..."},
  "impact_events": [
    {
      "date": "...", "headline": "...", "session": "london",
      "price_change_30m": -2.3, "impact_label": "high_bearish",
      "time_since_last_event_hours": 72.5,
      "abnormal_return": -1.8, "ar_significant": true
    }
  ],
  "correlations": {
    "overall": {"pearson": -0.32, "p_value": 0.001, "sample_hours": 1872},
    "by_session": {
      "london": {"pearson": -0.41, "sample_hours": 450},
      "ny_regular": {"pearson": -0.18, "sample_hours": 890}
    }
  },
  "session_transitions": {
    "premarket_to_open": {"avg_gap_pct": 0.8, "news_correlation": 0.42}
  },
  "drawdown_events": [
    {
      "peak_date": "...", "trough_date": "...", "drop_pct": -12.3,
      "news_attributed_pct": 0.65,
      "high_impact_events_in_window": 4,
      "sessions_involved": ["london", "ny_regular"]
    }
  ],
  "baseline_anomalies": [
    {"date": "...", "z_score": 3.8, "deviation": "high", "session": "london"}
  ]
}
```

### Step 0f — Add Portfolio/Batch Endpoints
- `GET /correlation/batch?symbols=AAPL,MSFT,GOOG&from=...&to=...` returning per-symbol results
- This saves the Research Agent from making N parallel HTTP calls for N tickers

### Step 0g — Add Inter-session News Gap
- `compute_premarket_gap(symbol, date)` → "How many hours between last pre-market news and market open?"
- Important for gapping analysis — agents need to know if a stock is likely to gap at open

---

## Phase 0.5 — vinu_lib Shared Utilities (~4 days, parallel with Phase 0)

**Priority: HIGH** — Every service duplicates HTTP client setup, SQLite patterns, FastAPI boilerplate, and config parsing. Build once, reuse everywhere.

### Step 0.5a — ResilientClient (`vinu_lib/client.py`)
Replace duplicated httpx client creation across all services:

```python
class ResilientClient:
    def __init__(self, base_url, service_name, timeout=30.0, circuit_breaker_threshold=3):
        ...
    async def get(self, path, params=None, fallback=None) -> Union[dict, None]:
        # Circuit breaker (3 failures → open for 30s)
        # Exponential backoff retry (1s, 2s, 4s)
        # Fallback value on failure
        # Health check polling (every 30s, parallel)
    async def post(self, path, json=None, fallback=None) -> Union[dict, None]:
        ...
```

**Fallback defaults per service:**
| Caller → Target | Fallback When Down |
|-----------------|-------------------|
| vinu-strategy → vinu-features | Use built-in SMA from stock-price query engine |
| vinu-strategy → vinu-correlation | Skip correlation stage, run on price-only |
| vinu-correlation → vinu-news | Return empty impact (cache last known data) |
| vinu-simulator → vinu-strategy | Use equal-weight portfolio as baseline |
| vinu-research → any tool | Log warning, skip refinement, continue with best-so-far |

### Step 0.5b — Shared FastAPI Factory (`vinu_lib/server.py`)
```python
def create_app(service_name: str, version: str, router: APIRouter) -> FastAPI:
    # Standard CORS per used-ports.md
    # Standard error handlers (ValidationError, HTTPException, unhandled)
    # Standard middleware (request_id, timing, structured logging)
    # /health endpoint returning {ok: true, service, version, uptime}
    # OpenAPI metadata
```

### Step 0.5c — Shared Config (`vinu_lib/config.py`)
```python
@dataclass
class ServiceConfig:
    host: str
    port: int
    log_level: str
    env: str

def from_env(prefix: str) -> ServiceConfig:
    # Reads {PREFIX}_HOST, {PREFIX}_PORT, etc. from environment
    # with sensible defaults
```

### Step 0.5d — Shared SQLite Backend (`vinu_lib/sqlite.py`)
- `BaseBackend` class with WAL mode, connection pool, thread safety, migration pattern
- Extracted from duplicated patterns in vinu-news, vinu-stock-price, vinu-strategy

### Step 0.5e — Shared Parquet Store (`vinu_lib/parquet.py`)
- `ParquetStore` base class with partition helpers, append, dedup, compact
- Extracted from duplicated patterns in vinu-stock-price, vinu-features, vinu-correlation

### Step 0.5f — Migrate Existing Services
After building each shared utility, migrate all 5+ services to use them:
1. vinu-news
2. vinu-stock-price
3. vinu-features
4. vinu-correlation
5. vinu-strategy
6. vinu-simulator

---

## Phase 1 — vinu-features & vinu-simulator Enhancements (~1 day) ✅ DONE 2026-07-13

**Priority: MEDIUM** — Needed so the Research Agent can request indicators and run custom strategies mid-loop.

### Step 1a — vinu-features: On-Demand Indicator API
**Current state:** Batch-only (submit request → worker polls → complete). The Research Agent needs instant replies.

**What to build:**
- `GET /indicators/{ticker}?kinds=sma_20,rsi_14,adx_14&from=...&to=...` returning values immediately
- No worker — compute inline for requested kinds
- Cache results (TTL 60s since trades don't change)
- Python wrapper: `get_indicator_values(symbol, kinds, from_ts, to_ts) → pd.DataFrame`

### Step 1b — vinu-simulator: Custom Strategy Evaluation
**Current state:** Only evaluates named strategies via vinu-strategy HTTP. The Quant Coder Agent generates custom Python code that needs to run.

**What to build:**
- `BaseStrategy` abstract class:
```python
class BaseStrategy:
    def generate_weights(self, data: pd.DataFrame) -> pd.Series:
        """Return target weights (long/short/cash)."""
        raise NotImplementedError
```
- `simulate_custom(strategy_class, symbols, from_ts, to_ts, config) → SimulationResult`
  - Accepts a Python class (or dotted path), not just a YAML name
  - Returns Sharpe, MaxDD, WinRate, trade log, equity curve
- Template system so the Quant Coder just fills in the `generate_weights` method

---

## Phase 2 — vinu-research: Agentic Strategy Researcher (~5 days)

**Priority: HIGHEST** — This is the main deliverable. The thing the user interacts with.

### Step 2a — Define Agent System Prompts

**Quant Coder Agent:**
```
You are an expert quantitative researcher and Python developer.
Your job is to:
1. Take the user's strategy idea and turn it into runnable Python code
2. Call vinu-features to get indicator data
3. Call vinu-simulator to backtest the strategy
4. Parse the Risk Critic's feedback and refine the strategy
5. Generate: ADX filters, session filters, news cooling-off periods,
   volatility guards, position sizing rules

You have access to these tools:
- get_indicators(ticker, kinds, from_ts, to_ts) -> DataFrame
- run_backtest(strategy_code, tickers, from_ts, to_ts) -> SimulationResult
- get_story(ticker, from_ts, to_ts) -> StoryBlock (for reference)

Output format: Python class inheriting from BaseStrategy with
generate_weights(self, data) method.
```

**Risk Critic Agent:**
```
You are an expert risk manager and trading psychologist.
Your job is to:
1. Read backtest results (Sharpe, MaxDD, WinRate, trade log)
2. Query vinu-correlation story blocks to understand WHY drawdowns happened
3. Identify patterns: session-specific losses, news-driven spikes, choppy markets
4. Suggest specific, implementable refinements
5. Know when to stop: if Sharpe hasn't improved in 2 iterations, stop

You have access to these tools:
- get_story(ticker, from_ts, to_ts) -> StoryBlock
- get_drawdowns(ticker, from_ts, to_ts) -> DrawdownEvents

Output format:
- "PASS" + reason (if strategy is acceptable)
- "REFINE" + specific suggestions (if improvements exist)
- "STOP" + explanation (if strategy is fundamentally flawed)
```

### Step 2b — Build Tool Wrappers
Python API wrappers that the agents call (not HTTP — direct Python for speed):

```python
class ResearchTools:
    async def get_indicators(self, symbol: str, kinds: list[str], from_ts, to_ts) -> pd.DataFrame:
        # Calls vinu-features on-demand API (or direct library if co-located)

    async def run_backtest(self, strategy_class: type[BaseStrategy],
                           symbol: str, from_ts, to_ts) -> SimulationResult:
        # Calls vinu-simulator custom strategy API
        # Returns Sharpe, MaxDD, WinRate, trade_log, equity_curve

    async def get_story(self, symbol: str, from_ts, to_ts) -> StoryBlock:
        # Calls vinu-correlation GET /story/{symbol}
        # Returns the consolidated story block JSON

    async def get_drawdowns(self, symbol: str, from_ts, to_ts) -> list[DrawdownEvent]:
        # Calls vinu-correlation GET /drawdown/{symbol}
        # Returns structured drawdown events
```

### Step 2c — Build Loop Orchestrator

```python
class StrategyResearchLoop:
    def __init__(self, tools: ResearchTools, config: ResearchConfig):
        self.tools = tools
        self.config = config  # max_iterations=5, improvement_threshold=0.05

    async def run(self, user_idea: str, symbol: str, from_ts, to_ts) -> ResearchResult:
        best_result = None
        history = []

        for iteration in range(self.config.max_iterations):
            # Phase A: Quant Coder generates/refines strategy
            if iteration == 0:
                strategy_code = await self.quant_coder.create_from_idea(user_idea)
            else:
                strategy_code = await self.quant_coder.refine(
                    last_result, critic_feedback)

            # Phase B: Run backtest
            result = await self.tools.run_backtest(
                strategy_code, symbol, from_ts, to_ts)

            # Phase C: Risk Critic evaluates
            story = await self.tools.get_story(symbol, from_ts, to_ts)
            critic_feedback = await self.risk_critic.evaluate(result, story)

            history.append({"iteration": iteration, "result": result,
                          "critique": critic_feedback, "story": story})

            # Phase D: Check stop conditions
            if critic_feedback.verdict == "STOP":
                break
            if critic_feedback.verdict == "PASS":
                best_result = result
                break
            if iteration > 1 and not self._is_improving(history):
                break

            best_result = result

        return await self._generate_report(history, best_result)
```

### Step 2d — Build Strategy Code Generator
Template system that takes the user's idea and produces a draft `BaseStrategy`:

```python
# Template for basic crossover
class UserStrategy(BaseStrategy):
    def __init__(self, fast_period=20, slow_period=50):
        self.fast = fast_period
        self.slow = slow_period

    def generate_weights(self, data):
        # data has: open, high, low, close, volume, plus requested indicators
        fast_ma = data['close'].rolling(self.fast).mean()
        slow_ma = data['close'].rolling(self.slow).mean()
        signal = (fast_ma > slow_ma).astype(int).diff()
        # signal=1 = buy, signal=-1 = sell, 0 = hold
        return signal * 0.98  # max 98% allocation
```

The Quant Coder fills in the `generate_weights` method. After refinement, adds filters:
```python
# After Risk Critic feedback: add ADX filter + session filter
class RefinedStrategy(BaseStrategy):
    def generate_weights(self, data):
        fast_ma = data['close'].rolling(20).mean()
        slow_ma = data['close'].rolling(50).mean()
        adx = data['adx_14']
        session = data['session']

        signal = (fast_ma > slow_ma).astype(int).diff()

        # ADX filter: no trade if ADX < 20 (choppy market)
        signal[adx < 20] = 0

        # Session filter: no London session
        signal[session == 'london'] = 0

        # News cooling-off: skip 60min after high-impact news
        # (requires news_impact column from correlation service)
        # signal[data['news_cooldown']] = 0

        return signal * 0.98
```

### Step 2e — Build Research Report Generator

```markdown
=== FINAL RESEARCH REPORT ===
Strategy: SMA20/SMA50 Crossover (refined)
Ticker: AAPL
Time Period: 2025-01-01 → 2025-12-31

Refinements Applied:
  1. ADX filter (>20) - avoids choppy sideways markets
  2. London session exclusion (07:00-13:00 UTC) - high news volatility
  3. News cooling-off period (skip 60min after impact>medium)
  4. Earnings week position sizing (-50%)

Before → After:
  Sharpe:         0.72 → 1.35
  Max Drawdown:  -18.3% → -6.2%
  Win Rate:      51% → 61%
  Total Return:  +8.2% → +14.7%
  News-driven losses avoided: 4 major events

Confidence Assessment:
  NY Regular Session: HIGH (Sharpe 1.6 in this regime)
  London Session:     LOW (avoid — Sharpe 0.3)
  Earnings Weeks:     MEDIUM (reduce position size)
  Low ADX Periods:    LOW (flat/choppy — skip entirely)

Key Findings:
  1. The strategy lost most money during London session news events
  2. ADX filter eliminated losses in Q3 2025 (sideways market)
  3. News cooling-off prevented 2 major gap-down captures

Optimized Strategy Code: saved to output/aapl_sma20_50_refined.py
```

### Step 2f — Build CLI Entry Point

```
$ vinu-research run "test SMA20/SMA50 crossover on AAPL for 2025"

[vinu-research] Strategy: SMA20/SMA50 Crossover
[vinu-research] Ticker: AAPL
[vinu-research] Period: 2025-01-01 → 2025-12-31
[vinu-research] Max iterations: 5
─────────────────────────────────────────
[Iteration 1/5] Quant Coder: Created basic crossover...
[Iteration 1/5] Simulator: Sharpe=0.72, MaxDD=-18.3%, WinRate=51%
[Iteration 1/5] Risk Critic: Checking story blocks...
  → 3 drawdowns in London session (high news volatility)
  → 2 drawdowns within 2h of bearish events
  → SUGGESTION: Add ADX filter + skip London session + news cooldown
─────────────────────────────────────────
[Iteration 2/5] Quant Coder: Refining with ADX>20, London skip, cooldown...
... (continues until done)
```

### Step 2g — Add Progress Streaming
- Real-time output showing each iteration
- Agent reasoning printed as it happens
- Tool calls visible (what data was fetched, what the simulator returned)
- Final report printed at the end

---

## Phase 3 — Integration & Polish (~2 days)

### Step 3a — End-to-End Flow
- Wire: CLI → research loop → tools → backtest → report
- Ensure all Phase 0 and Phase 1 changes are wired together
- Run: `vinu-research run "test SMA20/SMA50 on AAPL 2025"` end-to-end

### Step 3b — Iteration Limits & Stop Conditions
- Configurable max iterations (default 5)
- Auto-stop: if Sharpe hasn't improved >0.05 in 2 consecutive iterations
- Auto-stop: if the Risk Critic returns "STOP" (strategy fundamentally flawed)
- Auto-stop: if MaxDD exceeds a configurable threshold (protect against bad strategies)

### Step 3c — Human-in-the-Loop Checkpoint
- After final iteration, print report and ask user: "Approve this strategy for use?"
- Strategy code is saved to a file regardless
- Only "approved" strategies are marked ready for vinu-strategy

### Step 3d — Progress Streaming UX
- Real-time console output
- Clear iteration markers
- Agent reasoning visible (truncated to key points)
- Tool calls shown with their results (metrics, story highlights)
- Final report as formatted Markdown

---

## Phase 4 — vinu-agents: LLM Narrative Layer (~4.5 days, optional)

**Priority: OPTIONAL** — The system works without this. Raw story blocks are enough for the Risk Critic to make decisions. LLM adds richer narrative.

### Step 4a — LLM Integration
- Ollama/OpenAI client with configurable model, temperature, max_tokens
- Works with local models (Mistral, Llama) or cloud (GPT-4, Claude)

### Step 4b — Article Analyst
- Takes raw article → prompt → structured JSON:
```json
{
  "sentiment": -0.7,
  "confidence": 0.85,
  "risk_flags": ["downgrade", "revenue_warning"],
  "tickers": ["AAPL"],
  "summary": "Morgan Stanley downgrades Apple citing weak iPhone demand"
}
```

### Step 4c — Market Digest
- Groups multiple articles by ticker → daily summary with key themes
- Output: `GET /digest/AAPL?date=2025-03-15` → structured daily narrative

### Step 4d — Cache Layer
- SQLite table for LLM results keyed by article URL
- TTL configurable (default 24h)
- Same article never analyzed twice

### Step 4e — Wire into vinu-research (Optional)
- If vinu-agents is running, the Risk Critic also gets LLM-enhanced narrative
- If vinu-agents is down, falls back to raw story blocks
- The report includes an optional "Narrative Analysis" section

---

## Phase 5 — Future Components (Phase 2 from roadmap)

**Priority: FUTURE** — Build after the core research loop is working.

### vinu-core — Unified Platform
- Shared watchlist, symbol catalog, global config
- Cross-package settings bridge
- Pre-requisite: vinu_lib shared utilities

### vinu-orchestrator — Pipeline Automation
- Daily job: ingest news + prices → features → agents → strategy → sim or paper
- Single CLI / cron entry

### vinu-paper — Live Paper Trading
- Real-time paper matcher
- Same weight contract as vinu-execution
- Fill against live quotes without broker orders

### vinu-positions — Post-Trade Risk
- Open P&L tracking
- Trailing stops, take-profit
- Drawdown monitor

### vinu-risk — Portfolio Risk Overlay
- Sector caps, correlation limits
- Daily loss kill switch
- Max leverage enforcement

---

## Dependency Graph

```
vinu-correlation story blocks ──┐
                                 ├──> vinu_lib shared utilities
                                 │         │
vinu-features on-demand API ─────┤         │
                                 │         v
vinu-simulator custom eval ──────┘    vinu-research (AutoGen loop)
                                            │
                                            v
                                     Research Report
                                            │
                                            v
                                     Human Review
                                            │
                                            v
                                     vinu-strategy (finalized)
                                            │
                                            v
                                     vinu-simulator (re-validation)
                                            │
                                            v
                                     vinu-execution (live)
```

**Critical path:** Enhance vinu-correlation → Build vinu_lib → Enhance vinu-features + vinu-simulator → Build vinu-research → Integration

Everything else branches from these nodes. Phases 4 and 5 are independent and can be done in any order after the critical path is complete.

---

## Time Estimate Summary

| Phase | Duration | Depends On |
|-------|----------|-----------|
| Phase 0 — vinu-correlation story blocks | ~3 days | — |
| Phase 0.5 — vinu_lib shared utilities | ~4 days (parallel with Phase 0) | — |
| Phase 1 — vinu-features + vinu-simulator enhancements | ~1 day | Phase 0.5 (ResilientClient) |
| Phase 2 — vinu-research AutoGen loop | ~5 days | Phase 0 + Phase 1 |
| Phase 3 — Integration & Polish | ~2 days | Phase 2 |
| Phase 4 — vinu-agents LLM layer | ~4.5 days (optional) | Phase 0.5 (ResilientClient) |
| Phase 5 — Future components | Variable | All above |

**Critical path total:** ~11 days (Phases 0 → 1 → 2 → 3)
**With parallel Phase 0.5:** ~7-8 days
**Whole plan including optional phases:** ~19.5 days

---

## Current Immediate Next Actions

### Today — Start Phase 0, Step 0a
1. Open `vinu-correlation/engine/market_hours.py`
2. Add `london` session (07-15 UTC), `ny_premarket` (13-14:30 UTC)
3. Update `classify_session()` to return the new sessions
4. Update `engine/impact.py` to use new sessions for window truncation
5. Update `engine/correlation.py` to filter by session name
6. Update schemas and API responses
7. Run existing tests to verify nothing broke

### Today — Start Phase 0.5, Step 0.5a (parallel)
1. Create `vinu_lib/client.py` with `ResilientClient`
2. Create `vinu_lib/server.py` with `create_app()`
3. Create `vinu_lib/config.py` with `from_env()`
4. These can be built independently of Phase 0

## Phase 1 Delivery Summary

### Step 1a — vinu-features On-Demand Indicator API ✅
- `GET /indicators/{ticker}?kinds=sma_20,rsi_14&from=...&to=...` — computes indicators inline
- `GET /indicators` — lists available indicator kinds
- 60s TTL cache, reuses existing `StockPriceClient` + `apply_indicators()`
- 4 new tests passing

### Step 1b — vinu-simulator Custom Strategy Evaluation ✅
- `BaseStrategy` abstract class with `generate_weights(data) → pd.Series`
- Per-ticker combining with abs-normalization → existing `WeightSimulator`
- `POST /simulate/custom` HTTP endpoint (execs Python strategy code)
- `SimulatorAPI.simulate_custom()` Python API
- Features client for vinu-features indicator integration
- `get_ohclv()` on PriceClient for full bar data
- 7 new tests passing

### Documentation ✅
- vinu-features `ch10-http-api.md` updated with indicator routes
- vinu-simulator `docs/book/` created (11 files: INDEX, ARCHITECTURE, 0-7 chapters)
- `20260713-phase1-effects.json` reference file created
- Phase 1 marked DONE in plan

**Total: 69/69 tests passing across both services.**
