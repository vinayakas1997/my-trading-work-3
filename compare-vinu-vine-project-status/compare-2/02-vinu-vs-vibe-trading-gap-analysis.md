# Vinu-Agent vs Vibe-Trading: Comprehensive Gap Analysis

> **Generated**: 2026-07-15
>
> **Scope**: Compares `vinu-agent` (vinu-components/vinu-agent/) against `Vibe-Trading` (personal-important/other-reference-repos/Vibe-Trading/)
>
> **Methodology**: Source code review of both repos + integration tests on vinu-agent

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Bug-Level Fixes (Will Crash Production)](#2-bug-level-fixes-will-crash-production)
3. [Missing Features by Category](#3-missing-features-by-category)
4. [What Vinu-Agent Does Better](#4-what-vinu-agent-does-better)
5. [Feature Equivalence Map](#5-feature-equivalence-map)
6. [Combined Priority Action Plan](#6-combined-priority-action-plan)
7. [Detailed Feature Descriptions](#7-detailed-feature-descriptions)
8. [Appendix: Source File Reference](#8-appendix-source-file-reference)

---

## 1. Executive Summary

| Dimension | Vibe-Trading | Vinu-Agent | Gap Severity |
|-----------|-------------|------------|--------------|
| **Total LOC** | ~203k Python | ~8k Python (agent) + ~50k (7 services) | Architectural choice |
| **Tests** | 258 test files | 62 test files | ⚠️ Low (younger project) |
| **Architecture** | Monolith | 7 microservices + shared lib | ✅ Vinu advantage |
| **Skills** | 87 bundled | 5 written (15 planned) | 🔴 Huge gap |
| **Swarm Presets** | 30 | 4 | 🟡 Medium gap |
| **IM Channels** | 16 | 2 planned (stubs) | 🔴 Huge gap |
| **LLM Providers** | 22 | 1 (OpenAI only) | 🟡 Medium gap |
| **Data Loaders** | 22 sources | 4 sources | 🔴 Huge gap |
| **Broker Connectors** | 12 brokers | 0 | 🔴 Huge gap |
| **Alpha Factors** | 461 pre-built | 19 basic operators | 🔴 Huge gap |
| **Live Trading** | Full system (mandate, guard, kill switch) | 0 | 🔴 Huge gap |
| **Web Frontend** | Full React 19 UI | 0 | 🟡 Medium gap |
| **MCP Server** | 54 tools exposed | 0 | 🟡 Medium gap |
| **Security** | Production-hardened (Docker, API, CI gates) | Basic | 🟡 Medium gap |

### Key Finding
**Vinu-agent is architecturally superior** (microservices, centralized security library, `ResilientClient`, better test isolation) but **massively behind in breadth** (features, data sources, broker integrations, skills). Vibe-Trading is a feature-rich monolith; vinu-agent is a clean foundation that needs content.

---

## 2. Bug-Level Fixes (Will Crash Production)

These are defects in the current vinu-agent source code that will cause runtime failures.

| # | Bug | File | Impact | Fix |
|---|-----|------|--------|-----|
| 1 | **Missing `_fix_tool_pairs()`** | `agent/loop.py:276-296` | `_auto_compact` strips history to 3 messages. If the last message has a `tool_call` with `id:X`, its matching `tool_result` (role:"tool", tool_call_id:"X") is dropped. OpenAI API returns **400 error** on next request because tool results must exactly match tool call IDs. **This WILL crash long sessions.** | After compaction, scan for orphaned `tool_call` messages and inject dummy `tool_result` entries for any missing IDs |
| 2 | **No per-tool timeout** | `agent/loop.py:172-218` | `ThreadPoolExecutor.submit()` and direct `.execute()` calls have **no timeout**. If the features API hangs (30s default timeout in httpx, but some tools have 60s or 300s), the agent loop freezes indefinitely. All iterations stall. | Add `concurrent.futures.wait()` with `timeout=` around each tool execution; catch `TimeoutError` |
| 3 | **No iteration wrap-up nudge** | `agent/loop.py:64-167` | When iteration == `max_iterations - 1`, the agent may still be mid-tool-call. On the next loop iteration, `max_iterations` is reached, and a generic "I've reached max iterations" message is returned — **no useful output**. | At 80% of max_iterations, inject a system message: "You have X iterations remaining. Wrap up your analysis." |
| 4 | **Tool call pairing after context collapse** | `agent/loop.py:263-273` | Same root cause as #1 but in `_context_collapse`. When a message body is truncated (head + `...[collapse]...` + tail), its `tool_call_id` is preserved but the matching result might be lost if the `tool` role message was collapsed to a different index. | Same fix as #1 — post-compaction pair validation |
| 5 | **Missing agent self-description SKILL.md** | `skills/` (no file) | The agent has no `agent/SKILL.md` describing itself. The `load_skill` tool cannot return "who is the agent." The system prompt has no self-referential knowledge. | Create `skils/agent-self/SKILL.md` with the agent's own metadata |

### Already Fixed (in current session)
| Bug | Status | Fix |
|-----|--------|-----|
| ContextBuilder bypassed (no system prompt) | ✅ Fixed | Wired into `SessionService._run_with_agent` |
| User message discarded (`messages[:-1]`) | ✅ Fixed | Removed slice |
| Broken tool dependency injections | ✅ Fixed | `build_registry()` now passes all deps |
| Research port conflict (8086 vs 8086) | ✅ Fixed | Changed to 8087 |
| features_tool route (`/features/submit`) | ✅ Fixed | Changed to `/requests` with epoch timestamps |
| stock_price_tool `from` type (string vs int) | ✅ Fixed | Converted to Unix timestamps |
| strategy_tool route (`/strategy/evaluate`) | ✅ Fixed | Changed to `/strategies/{name}/evaluate` |
| news_tool route (`/news/query`) | ✅ Fixed | Changed to `/search?q=...` |
| SSE event loop never set | ✅ Fixed | Added FastAPI lifespan |
| Skills dir default (empty `~/.vinu/skills`) | ✅ Fixed | Now points to repo `./skills/` |
| LLM client recreated per call | ✅ Fixed | Cached in `_get_client()` |
| Missing `Attempt.from_dict()` | ✅ Fixed | Added classmethod |
| Empty frontmatter regex fail | ✅ Fixed | Made `\n` optional in closing pattern |

---

## 3. Missing Features by Category

### 3.1 Agent Core (ReAct Loop)

| Feature | Vibe-Trading | Vinu-Agent | Effort |
|---------|-------------|------------|--------|
| LLM provider abstraction (`ChatLLM`) | 22 providers | 1 (OpenAI) | Low |
| Streaming LLM responses | ✅ Full | ❌ | Low |
| Progress events (`ProgressEvent` + `HeartbeatTimer`) | ✅ Structured | ❌ | Low |
| Trace system (crash-safe JSONL + sidecar files) | ✅ | ❌ | Low |
| Tool result redaction (sensitive field masking) | ✅ | ❌ | Low |
| Compact tool (explicit L3 trigger) | ✅ | ❌ | Low |
| Workspace memory (runtime state per agent invocation) | ✅ | ❌ | Low |
| Content filter skip handling | ✅ | ❌ | Low |
| Token usage tracking (per-iteration, per-model) | ✅ Basic estimate only | ❌ | Low |
| `_fix_tool_pairs()` after context compaction | ✅ | ❌ | Critical |
| Per-tool timeout enforcement | ✅ | ❌ | Critical |
| Iteration wrap-up nudge (80% rule) | ✅ | ❌ | Medium |

### 3.2 Tool System

| Tool | Vibe-Trading | Vinu-Agent | Effort |
|------|-------------|------------|--------|
| `backtest` | ✅ | ✅ (via vinu-simulator) | Already works |
| `get_market_data` | ✅ | ✅ (stock_price_tool) | Already works |
| `get_stock_news` | ✅ | ✅ (news_tool) | Already works |
| `web_search` | ✅ | ✅ (web_search_tool) | Already works |
| `load_skill` | ✅ | ✅ | Already works |
| `remember` | ✅ | ✅ | Already works |
| `session_search` | ✅ | ✅ | Already works |
| `get_fundamentals` | ✅ | ❌ | Low (wrap vinu-research) |
| `get_sec_filings` | ✅ | ❌ | Low (wrap SEC API) |
| `get_financial_statements` | ✅ | ❌ | Low |
| `get_options_chain` | ✅ | ❌ | Low |
| `get_macro_series` (FRED) | ✅ | ❌ | Low |
| `screen_market` | ✅ | ❌ | Medium |
| `factor_analysis` | ✅ | ❌ | Medium (wrap vinu-features) |
| `pattern` (pattern recognition) | ✅ | ❌ | Medium |
| `read_document` (PDF/DOCX) | ✅ | ❌ | Low |
| `read_url` | ✅ | ❌ | Low |
| `analyze_image` (vision/OCR) | ✅ | ❌ | Low |
| `bash` (sandboxed subprocess) | ✅ | ❌ | High |
| `compact` (force context compaction) | ✅ | ❌ | Low |
| `create_hypothesis` / CRUD | ✅ | ❌ | Low (wrap vinu-research) |
| `background_run` / `check_background` | ✅ | ❌ | Medium |
| `run_swarm` | ✅ | ✅ | Already works |
| MCPRemoteTool (dynamic MCP proxy) | ✅ | ❌ | Medium |

### 3.3 Skills Library

| Category | Vibe-Trading | Vinu-Agent | Effort |
|----------|-------------|------------|--------|
| **Data source skills** | 10 (akshare, eastmoney, yfinance, ccxt, etc.) | 0 | Low (just SKILL.md files) |
| **Strategy skills** | 7 (strategy-generate, backtest-diagnose, execution-model, ml-strategy, etc.) | 3 (strategy-generate, backtest-diagnose, execution-model) | Low |
| **Technical analysis** | 9 (technical-basic, candlestick, ichimoku, harmonic, elliott-wave, etc.) | 0 | Low |
| **Fundamental analysis** | 5 (fundamental-filter, financial-statement, valuation-model, etc.) | 0 | Low |
| **Factor research** | 5 (factor-research, multi-factor, alpha-zoo, etc.) | 1 (factor-research) | Low |
| **Risk analysis** | 5 (risk-analysis, volatility, correlation-analysis, etc.) | 0 | Low |
| **Macro analysis** | 5 (global-macro, macro-analysis, fred-macro, commodity, cross-market) | 0 | Low |
| **Sector/thematic** | 4 (sector-rotation, etf-analysis, fund-analysis, fund-selection) | 0 | Low |
| **Equity** | 8 (adr-hshare, hk-connect, ashare-st-filter, corporate-events, etc.) | 0 | Low |
| **Options & derivatives** | 5 (options-advanced, options-payoff, crypto-derivatives, etc.) | 0 | Low |
| **Crypto/DeFi** | 5 (onchain-analysis, defi-yield, stablecoin-flow, etc.) | 0 | Low |
| **Sentiment** | 3 (sentiment-analysis, social-media-intelligence, behavioral-finance) | 0 | Low |
| **Quant/ML** | 4 (ml-strategy, pair-trading, stat-arb, seasonal) | 0 | Low |
| **Specialized** | 10 (shadow-account, trade-journal, thesis-tracker, regulatory, etc.) | 2 (research-discipline, report-generate) | Low |
| **Self-description** | 1 (agent/SKILL.md) | 0 | Low |
| **Total** | **87** | **5** | **~2 days to write 82** |

**Key insight**: Skills are pure Markdown files with YAML frontmatter — zero code required. Each takes ~15-30 minutes to write. The 82 missing skills represent ~20-40 hours of content work.

### 3.4 Swarm Presets

| Preset | Vibe-Trading | Vinu-Agent |
|--------|-------------|------------|
| `investment_committee` | ✅ | ✅ |
| `quant_strategy_desk` | ✅ | ✅ |
| `risk_committee` | ✅ | ✅ |
| `research_team` | ✅ | ✅ |
| `equity_research_team` | ✅ | ❌ |
| `fundamental_research_team` | ✅ | ❌ |
| `technical_analysis_panel` | ✅ | ❌ |
| `macro_strategy_forum` | ✅ | ❌ |
| `crypto_research_lab` | ✅ | ❌ |
| `crypto_trading_desk` | ✅ | ❌ |
| `factor_research_committee` | ✅ | ❌ |
| `global_allocation_committee` | ✅ | ❌ |
| `sector_rotation_team` | ✅ | ❌ |
| `sentiment_intelligence_team` | ✅ | ❌ |
| `earnings_research_desk` | ✅ | ❌ |
| `event_driven_task_force` | ✅ | ❌ |
| `derivatives_strategy_desk` | ✅ | ❌ |
| `statistical_arbitrage_desk` | ✅ | ❌ |
| `pairs_research_lab` | ✅ | ❌ |
| `ml_quant_lab` | ✅ | ❌ |
| `portfolio_review_board` | ✅ | ❌ |
| `value_investing_committee` | ✅ | ❌ |
| `social_alpha_team` | ✅ | ❌ |
| `global_equities_desk` | ✅ | ❌ |
| `macro_rates_fx_desk` | ✅ | ❌ |
| `commodity_research_team` | ✅ | ❌ |
| `convertible_bond_team` | ✅ | ❌ |
| `credit_research_team` | ✅ | ❌ |
| `etf_allocation_desk` | ✅ | ❌ |
| `fund_selection_panel` | ✅ | ❌ |
| `geopolitical_war_room` | ✅ | ❌ |
| **Total** | **30** | **4** |

### 3.5 IM Channels

| Channel | Vibe-Trading | Vinu-Agent | Effort |
|---------|-------------|------------|--------|
| Telegram | ✅ (1,674 LOC) | ✅ Planned (stub) | High |
| Discord | ✅ (818 LOC) | ✅ Planned (stub) | Medium |
| Slack | ✅ (740 LOC) | ❌ | Medium |
| WhatsApp | ✅ | ❌ | Medium |
| Signal | ✅ | ❌ | Medium |
| WeChat | ✅ | ❌ | High |
| QQ / NapCat | ✅ | ❌ | Medium |
| Feishu / Lark | ✅ | ❌ | Medium |
| DingTalk | ✅ | ❌ | Medium |
| Microsoft Teams | ✅ | ❌ | Medium |
| Matrix | ✅ | ❌ | Medium |
| Email | ✅ | ❌ | Low |
| WebSocket | ✅ | ❌ | Low |
| Mochat | ✅ | ❌ | High |
| Slack | ✅ | ❌ | Medium |
| Custom (entry point) | ✅ | ❌ | Low |
| **Total** | **16** | **2 planned (0 built)** | **~3 days to build first 2** |

### 3.6 Backtesting & Data

| Feature | Vibe-Trading | Vinu-Agent | Gap |
|---------|-------------|------------|-----|
| Backtest engines | 9 (China A, India, Global, Crypto, Futures, Forex, Options, Composite) | 1 (WeightSimulator) | 🔴 |
| Data loaders | 22 (tushare, yfinance, akshare, ccxt, baostock, tiingo, etc.) | 4 (Alpaca, Polygon, Yahoo, local) | 🔴 |
| Evaluation models | 11 (metrics, correlation, benchmark, validation, etc.) | 3 (sharpe, maxdd, profit factor) | 🟡 |
| Portfolio optimizers | 5 (mean-variance, risk-parity, max-div, equal-vol, turnover-aware) | 0 | 🔴 |
| Alpha factors | 461 (qlib158 + alpha101 + gtja191 + academic + fundamental) | 19 basic operators | 🔴 |
| Factor analysis | Full (IC/IR, quantile, comparison, bench runners) | Basic (in vinu-features) | 🟡 |

### 3.7 Live Trading

| Component | Vibe-Trading | Vinu-Agent | Effort |
|-----------|-------------|------------|--------|
| Broker connectors | 12 (Alpaca, IBKR, Binance, Robinhood, OKX, Futu, etc.) | 0 | Very high |
| Mandate model | User-committed trading mandate (universe, size, limits) | 0 | Very high |
| Order guard | Pre-trade checks + kill switch | 0 | Very high |
| Enforcement | Exclusion lists, asset class, notional, exposure, leverage, daily count | 0 | Very high |
| Kill switch | Filesystem sentinel (global + per-broker) | 0 | High |
| Tool classification | Tier 1 → Tier 2 → default-deny for read/write safety | 0 | High |
| Advisory | PreTradeAdvisoryInterface — opt-in review | 0 | High |
| Audit trail | Full order audit | 0 | Medium |
| Runtime | Scheduler, liveness, reconcile, triggers, flatten | 0 | Very high |

### 3.8 Infrastructure & DevOps

| Feature | Vibe-Trading | Vinu-Agent | Effort |
|---------|-------------|------------|--------|
| Docker Compose | Hardened (read-only rootfs, `cap_drop`, resource limits) | Basic (no security hardening) | Low |
| CI/CD | `.github/` workflows, Dependabot, hash-pinned deps | None | Low |
| API auth | Bearer token + CORS allowlist + CSRF + DNS rebinding guard | None | Medium |
| Rate limiting | On correlation endpoint | None | Low |
| SSE auth tickets | 60-second single-use tickets | None | Low |
| Multi-stage Docker build | Frontend + Python in one image | Single-stage Python only | Low |
| AST sandboxing | Backtest runner forbids network/subprocess/eval | None (vinu-lib has AST guard) | Already partially covered |
| CI environment gates | `os.getenv` usage banned in CI | Not needed (centralized config) | Already better |

---

## 4. What Vinu-Agent Does Better

| Feature | Vinu-Agent Advantage |
|---------|----------------------|
| **Architecture** | 7 microservices + shared library vs Vibe-Trading's monolith. Each service has its own Docker container, port, and can be scaled independently. |
| **Security library** | `vinu-lib/security/` is a single centralized package. Vibe-Trading's security is dispersed across 3+ modules (`src/security/`, `src/api/security.py`, `backtest/runner.py`). |
| **Resilient client** | `vinu-lib/ResilientClient` wraps circuit breaker, retry, timeout, and SSRF defense in one class. Vibe-Trading has ad-hoc retry/breaker logic duplicated across tools. |
| **Test isolation** | 500+ tests across 7 services, each service tested independently. Vibe-Trading's 258 tests are in one monolithic directory. |
| **Scheduled research** | `vinu-research/scheduled/` — cron + interval executor with job persistence. Equivalent to Vibe-Trading's `scheduled_research/`. |
| **Hypothesis registry** | `vinu-research/hypothesis_registry.py` — file-based JSON hypothesis store with token search. Equivalent to Vibe-Trading's `hypotheses/`. |
| **Strategy decay management** | `vinu-research/decay.py` + `storage/strategy_store.py` — full lifecycle (CREATED → DECAYED). Equivalent to Vibe-Trading's `strategy_store/`. |
| **Shadow account** | `vinu-research/shadow/` — extract → backtest → render pipeline. Equivalent to Vibe-Trading's `shadow_account/`. |
| **Walk-forward validation** | `vinu-simulator` — Monte Carlo, bootstrap, walk-forward. Equivalent to Vibe-Trading's backtest validation. |
| **Configuration system** | Centralized `config.py` with env var overrides, Pydantic schemas. Vibe-Trading's `env_schema.py` is similar but more complex. |
| **Run cards** | `run_card.md` + `run_card.json` output per backtest. Equivalent to Vibe-Trading's run card system. |
| **GPU support** | ML models can optionally use CUDA via PyTorch. Vibe-Trading has no ML training. |

---

## 5. Feature Equivalence Map

| Feature | Vibe-Trading File(s) | Vinu-Agent Equivalent |
|---------|---------------------|----------------------|
| ReAct loop | `agent/src/agent/loop.py` | `vinu_agent/agent/loop.py` |
| Tool system | `agent/src/agent/tools.py` | `vinu_agent/agent/tools.py` |
| Context builder | `agent/src/agent/context.py` | `vinu_agent/agent/context.py` |
| Skills loader | `agent/src/agent/skills.py` | `vinu_agent/agent/skills.py` |
| Frontmatter parser | `agent/src/agent/frontmatter.py` | `vinu_agent/agent/frontmatter.py` |
| Session store | `agent/src/session/store.py` | `vinu_agent/session/store.py` |
| Event bus (SSE) | `agent/src/session/events.py` | `vinu_agent/session/events.py` |
| Session service | `agent/src/session/service.py` | `vinu_agent/session/service.py` |
| Persistent memory | `agent/src/memory/persistent.py` | `vinu_agent/memory/persistent.py` |
| Swarm runtime | `agent/src/swarm/runtime.py` | `vinu_agent/swarm/runtime.py` |
| Swarm store | `agent/src/swarm/store.py` | `vinu_agent/swarm/store.py` |
| Swarm models | `agent/src/swarm/models.py` | `vinu_agent/swarm/models.py` |
| Worker (swarm) | `agent/src/swarm/worker.py` | `vinu_agent/swarm/worker.py` |
| Progress events | `agent/src/agent/progress.py` | ❌ Not implemented |
| Trace system | `agent/src/agent/trace.py` | ❌ Not implemented |
| Workspace memory | `agent/src/agent/memory.py` | ❌ Not implemented |
| Tool redaction | `agent/src/tools/redaction.py` | ❌ Not implemented |
| MCP integration | `agent/src/tools/mcp.py` | ❌ Not implemented |
| Hypothesis registry | `agent/src/hypotheses/` | `vinu-research/hypothesis_registry.py` |
| Strategy decay mgmt | `agent/src/strategy_store/` | `vinu-research/decay.py` |
| Shadow account | `agent/src/shadow_account/` | `vinu-research/shadow/` |
| Scheduled research | `agent/src/scheduled_research/` | `vinu-research/scheduled/` |
| Backtest engines | `agent/backtest/engines/` | `vinu-simulator/` |
| Data loaders | `agent/backtest/loaders/` | `vinu-stock-price/providers/` |
| Factor analysis | `agent/src/factors/` | `vinu-features/` |
| Live trading | `agent/src/live/` + `agent/src/trading/` | ❌ Not implemented |
| Alpha zoo | `agent/src/factors/zoo/` | ❌ Not implemented |
| Frontend | `frontend/` | ❌ Not implemented |
| MCP server | `agent/mcp_server.py` | ❌ Not implemented |
| IM channels | `agent/src/channels/` | ❌ Not implemented (stubs) |
| CLI | `agent/cli/` | `vinu_agent/cli.py` |

---

## 6. Combined Priority Action Plan

### P0 — Critical (fixes crashes, ships this week)

| # | Task | Est. Time | Files to Modify | Why |
|---|------|-----------|-----------------|-----|
| 1 | **`_fix_tool_pairs()` after auto_compact** | 2 hours | `agent/loop.py` — add post-compaction scan + dummy tool_result injection | Prevents OpenAI 400 errors on long sessions |
| 2 | **Per-tool timeout enforcement** | 2 hours | `agent/loop.py:_process_tool_calls` — wrap with `wait()` + `timeout=` | Prevents frozen agent loops |
| 3 | **Iteration wrap-up nudge** | 1 hour | `agent/loop.py:run` — inject system message at 80% iterations | Ensures last iteration produces useful output |
| 4 | **Agent self-description SKILL.md** | 30 min | Create `skills/agent-self/SKILL.md` | Agent knows own capabilities |
| 5 | **LLM provider abstraction** | 4 hours | Create `agent/llm.py` with `ChatLLM` ABC + OpenAI/DeepSeek/Ollama implementations | Unlocks DeepSeek ($0), Claude, Ollama |

### P1 — High Value (ships this month)

| # | Task | Est. Time | Files to Modify | Why |
|---|------|-----------|-----------------|-----|
| 6 | **Progress events + SSE streaming** | 4 hours | `agent/progress.py` + wire into `EventBus` | Real-time agent progress in UI |
| 7 | **Trace system** | 3 hours | `agent/trace.py` — JSONL writer + sidecar files | Debugging and audit trail |
| 8 | **Compact tool** (L3 trigger) | 1 hour | New `tools/compact_tool.py` | Agent voluntarily compresses context |
| 9 | **Write 15 Tier-2 skills** | 5 hours | Create 15 SKILL.md files | Covers fundamentals, risk, macro, crypto, options |
| 10 | **`get_fundamentals` tool** | 2 hours | New `tools/fundamentals_tool.py` wrapping vinu-research | Most-requested missing data |
| 11 | **Data loaders** (yfinance, tushare) | 6 hours | New loaders in vinu-stock-price/providers/ | Biggest data coverage gap |

### P2 — Foundation Features (ships next month)

| # | Task | Est. Time | Files to Modify | Why |
|---|------|-----------|-----------------|-----|
| 12 | **MCP server** | 2 days | New `mcp_server.py` + tool wrapping | Expose vinu tools to Claude Desktop/Cursor |
| 13 | **Telegram channel** | 2 days | New `channels/telegram.py` | Core UX promise of the plan |
| 14 | **Discord channel** | 1 day | New `channels/discord.py` | Second IM channel |
| 15 | **Write 26 more swarm presets** | 4 hours | 26 YAML files | 30 total vs 4 |
| 16 | **Docker security hardening** | 2 hours | Dockerfile + docker-compose.yml | Production safety (cap_drop, read_only) |
| 17 | **API auth + CORS** | 3 hours | `routes_system.py` + middleware | Production security |

### P3 — Enhancement (ships this quarter)

| # | Task | Est. Time | Notes |
|---|------|-----------|-------|
| 18 | **Web frontend** (React) | 2 weeks | Chat UI, backtest viewer, settings |
| 19 | **Alpha zoo** (461 factors) | 2 weeks | Port from Vibe-Trading's factor definitions |
| 20 | **Factor analysis tools** | 1 week | Wire IC/IR, quantile, bench runners to vinu-features |
| 21 | **Alpaca broker connector** (read-only) | 3 days | Paper trading data |
| 22 | **CLI subcommands** (swarm, channels, memory) | 3 days | Rich REPL with tab completion |
| 23 | **Write remaining 51 skills** | 2 days | Reach 87 total |

### P4 — Live Trading (long-term)

| # | Task | Est. Time | Notes |
|---|------|-----------|-------|
| 24 | **Broker connectors** (all 12) | 3 weeks | Read + write with mandate enforcement |
| 25 | **Live trading system** | 4 weeks | Mandate, order guard, kill switch, audit, halt |
| 26 | **Remaining IM channels** (12 more) | 2 weeks | WeChat, WhatsApp, Signal, Teams, etc. |

---

## 7. Detailed Feature Descriptions

### 7.1 `_fix_tool_pairs()` — Why It Matters

**The Problem**: OpenAI's chat completion API enforces `tool_call_id` integrity. Every message with `role: "tool"` must have a `tool_call_id` that matches an `id` in a `tool_calls` array from a previous `role: "assistant"` message. When vinu-agent's `_auto_compact()` or `_context_collapse()` removes messages, it can break this chain.

**Vibe-Trading's solution** (`agent/src/agent/loop.py`):
```python
def _fix_tool_pairs(self, messages: List[dict]) -> List[dict]:
    """After any compaction, ensure every tool_call has its matching result."""
    call_ids = set()
    for m in messages:
        for tc in m.get("tool_calls", []):
            call_ids.add(tc.get("id") or tc.get("function", {}).get("name", ""))
    result_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    orphan_ids = call_ids - result_ids
    for oid in orphan_ids:
        messages.append({
            "role": "tool",
            "tool_call_id": oid,
            "content": "{}",
        })
    return messages
```

**Implementation in vinu-agent**: Add this call to `_auto_compact()` (line 294, after the try/except) and `_context_collapse()` (line 273, before returning).

### 7.2 Per-Tool Timeout

**Vibe-Trading's solution**: Each `registry.execute()` call is wrapped with `concurrent.futures.wait()`:
```python
TOOL_TIMEOUT_SECONDS = 60

def _execute_with_timeout(self, name: str, params: dict) -> str:
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(self.registry.execute, name, params)
        try:
            return fut.result(timeout=TOOL_TIMEOUT_SECONDS)
        except TimeoutError:
            return f'{{"status": "error", "tool": "{name}", "error": "timeout after {TOOL_TIMEOUT_SECONDS}s"}}'
```

### 7.3 Iteration Wrap-Up Nudge

**Vibe-Trading's approach**: At 80% of `max_iterations`, inject a system message:
```python
if iteration >= int(self.max_iterations * 0.8):
    messages.append({
        "role": "system",
        "content": (
            f"You have {self.max_iterations - iteration} iteration(s) remaining. "
            "Wrap up your analysis and provide your final answer. "
            "Do NOT start new tool calls."
        ),
    })
```

### 7.4 LLM Provider Abstraction

**Vibe-Trading's `ChatLLM` interface** (`agent/src/agent/llm.py`):
```python
class ChatLLM(ABC):
    @abstractmethod
    def chat(self, messages: list, tools: Optional[list] = None, **kwargs) -> dict: ...
    @abstractmethod
    def chat_stream(self, messages: list, tools: Optional[list] = None, **kwargs) -> Generator[dict]: ...

class OpenAIChatLLM(ChatLLM): ...
class DeepSeekChatLLM(ChatLLM): ...  # Same API, different base_url
class AnthropicChatLLM(ChatLLM): ...  # Different message format
class OllamaChatLLM(ChatLLM): ...     # Local inference
```

### 7.5 Progress Events

**Vibe-Trading's system** (`agent/src/agent/progress.py`):
```python
@dataclass
class ProgressEvent:
    stage: str        # "tool_call", "llm_call", "compaction", "complete"
    current: int      # Current iteration
    total: int        # Max iterations
    message: str      # Human-readable status
    detail: dict      # Extra metadata (tool name, token count, etc.)

class HeartbeatTimer:
    """Fires a heartbeat event every N seconds so UI never looks frozen."""
    def __init__(self, interval: float = 5.0, callback: Callable): ...
    def start(self): ...
    def stop(self): ...
```

---

## 8. Appendix: Source File Reference

### Vibe-Trading Key Files

| File | LOC | Purpose |
|------|-----|---------|
| `agent/src/agent/loop.py` | 1,607 | ReAct engine with 5-layer context management |
| `agent/src/agent/tools.py` | 94 | BaseTool + ToolRegistry |
| `agent/src/agent/context.py` | 324 | ContextBuilder — system prompt + memory |
| `agent/src/agent/skills.py` | 182 | SkillsLoader — progressive disclosure |
| `agent/src/agent/progress.py` | 184 | ProgressEvent + HeartbeatTimer |
| `agent/src/agent/trace.py` | 284 | Crash-safe JSONL trace writer |
| `agent/src/agent/memory.py` | 53 | WorkspaceMemory (runtime state) |
| `agent/src/tools/` | 62 files | All tool definitions |
| `agent/src/tools/mcp.py` | — | MCP remote tool proxy |
| `agent/src/tools/redaction.py` | — | Tool result redaction |
| `agent/src/swarm/runtime.py` | 746 | DAG orchestration engine |
| `agent/src/swarm/worker.py` | 963 | Lightweight ReAct loop for workers |
| `agent/src/swarm/models.py` | — | SwarmRun, SwarmTask, etc. |
| `agent/src/swarm/store.py` | — | Swarm run persistence |
| `agent/src/swarm/presets/` | 30 YAML | Swarm preset definitions |
| `agent/src/session/` | 5 files | Session, events, search, store, service |
| `agent/src/memory/persistent.py` | 368 | File-based cross-session memory |
| `agent/src/channels/` | 25 files | 16 IM channel adapters |
| `agent/src/live/` | 11 modules | Live trading infrastructure |
| `agent/src/trading/connectors/` | 12 brokers | Broker API connectors |
| `agent/src/factors/zoo/` | 461 files | Alpha factor definitions |
| `agent/src/hypotheses/` | 2 modules | Hypothesis registry |
| `agent/src/strategy_store/` | 4 modules | Strategy lifecycle + decay |
| `agent/src/scheduled_research/` | 3 modules | Cron + interval jobs |
| `agent/src/shadow_account/` | 10 modules | Trade journal → backtest → report |
| `agent/backtest/engines/` | 9 engines | Multi-market backtesting |
| `agent/backtest/loaders/` | 33 loaders | Data source loaders |
| `agent/backtest/runner.py` | 1,128 | Backtest entrypoint |
| `agent/api_server.py` | 385 | FastAPI server |
| `agent/mcp_server.py` | 1,936 | MCP protocol server |
| `agent/cli/main.py` | 1,449 | CLI + REPL |
| `frontend/` | 14,800 LOC TypeScript | React 19 web UI |
| `agent/src/config/env_schema.py` | 364 | Centralized env config |

### Vinu-Agent Key Files

| File | LOC | Purpose |
|------|-----|---------|
| `vinu_agent/agent/loop.py` | 333 | ReAct engine |
| `vinu_agent/agent/tools.py` | 55 | BaseTool + ToolRegistry |
| `vinu_agent/agent/context.py` | 109 | ContextBuilder |
| `vinu_agent/agent/skills.py` | 90 | SkillsLoader |
| `vinu_agent/agent/frontmatter.py` | 35 | parse_frontmatter |
| `vinu_agent/tools/__init__.py` | 50 | Tool auto-discovery |
| `vinu_agent/tools/` | 11 tool files | Tool implementations |
| `vinu_agent/session/store.py` | 89 | SessionStore |
| `vinu_agent/session/events.py` | 75 | EventBus + SSE |
| `vinu_agent/session/models.py` | 135 | Session, Message, Attempt |
| `vinu_agent/session/service.py` | 171 | SessionService |
| `vinu_agent/session/search.py` | — | FTS5 search |
| `vinu_agent/swarm/runtime.py` | ~190 | DAG orchestration |
| `vinu_agent/swarm/worker.py` | ~65 | Worker ReAct loop |
| `vinu_agent/swarm/models.py` | ~130 | SwarmRun, SwarmTask |
| `vinu_agent/swarm/store.py` | ~50 | Swarm run persistence |
| `vinu_agent/server/app.py` | ~55 | FastAPI app factory |
| `vinu_agent/server/routes_*.py` | 4 files | API routes |
| `vinu_agent/service.py` | 115 | AgentService |
| `vinu_agent/config.py` | 66 | AgentConfig |
| `vinu_agent/memory/persistent.py` | — | PersistentMemory |
| `skills/` | 5 SKILL.md | Tier-1 skill files |

---

> **Generated for**: `vinu-components` (vinu-agent package)
>
> **Comparison source**: `Vibe-Trading` repository
>
> **Next action recommended**: Implement P0 items (fix_tool_pairs, timeouts, wrap-up nudge) before adding any new features. These are production-blocking bugs that will crash long agent sessions.
