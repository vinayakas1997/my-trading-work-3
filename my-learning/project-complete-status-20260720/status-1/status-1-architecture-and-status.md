# Project Status — 2026-07-20

## 0. How to read this document

Section 1 describes what exists today: every component, what it does, how they talk to
each other, and what each one is *for*. Section 2 states the aims each stage of the
pipeline currently achieves. Section 3 is the honest gap list — organized by category,
most granular first — between "what runs today" and "a self-reliant expert quant system
that manages a real portfolio." Section 4 is a phased methodology to close that gap.

Nothing in Section 1 is aspirational — every claim was verified against the actual code
(file paths, ports, function names) as of today, not against design docs.

---

## 1. Component architecture — what exists and how it coordinates

### 1.1 The pipeline, end to end

```
news-ingest ──┐
              ├──► news-api (8080) ──┐
stock-ingest ─┤                      │
              ├──► stock-api (8081) ─┼──► initial-analysis-compute ──► initial-analysis-api (8083)
              │                      │            (25 deterministic angles)
              └──► features-worker ──┴──► features-api (8082)                    │
                        (vinu-tools)     (indicators/factors/ML)                 │
                                                  │                              │
                                                  ▼                              ▼
                                          strategy-api (8084) ◄──────────────────┘
                                       (YAML rule engine → target weights)
                                                  │
                                                  ▼
                                          simulator-api (8085)
                                    (deterministic backtest engine — runs
                                     both vinu-strategy's YAML weights AND
                                     vinu-research's LLM/template Python
                                     strategies)
                                                  │
                                                  ▼
                                          research-api (8087)
                              (generate → backtest → critique → refine loop;
                               approved strategies become tracked "artifacts"
                               with decay monitoring)
                                                  │
                                                  ▼
                                            agent-api (8086)
                          (chat/orchestration; can call every service above as
                           a tool, plus a broker module for manual/paper trading)
                                                  │
                                                  ▼
                                         [ NOTHING — vinu-live does not exist ]
```

All twelve services above run continuously via `docker-compose.yml`
(`restart: unless-stopped`) once `docker compose up` is invoked. There is no cron
service in the stack — every "on a schedule" behavior is either an internal
`while True: sleep(...)` loop inside a long-running process (e.g. `vinu-strategy
schedule`, `vinu-research schedule-decay`), or a continuous ingest/compute loop
(`--continuous` flags on news/stock/initial-analysis).

### 1.2 Data layer — deterministic ingestion

- **vinu-news** (`news-api` :8080) — ingests news for watchlist tickers, continuous
  loop (`vinu-news-ingest --continuous`). Exports/syncs a shared watchlist file so
  other services (stock-price) pick up newly added tickers automatically.
- **vinu-stock-price** (`stock-api` :8081) — OHLCV ingestion, polls every 60s
  (`--interval 60`), 2023 backfill on ticker add, tracks per-symbol
  `backfill_status` in its catalog.
- **vinu-tools** (`features-api` :8082) — the feature/indicator/factor compute
  engine. Two processes: `features-worker` (background job runner, SQLite job
  registry, `ThreadPoolExecutor`-based, writes Parquet artifacts) and `features-api`
  (HTTP front end). Library includes ~25 classic TA indicators, the full WorldQuant
  **Alpha101** and **GTJA Alpha191** academic factor sets, Fama-French-style
  academic factors (HML/SMB/CMA/RMW/BAB/momentum), fundamental factors, bundled
  "recipes" (alpha158, alpha360, momentum, trend_pack, etc.), and a full ML
  sub-pipeline (CatBoost/LightGBM/XGBoost/RandomForest/linear models, labeling,
  preprocessing, feature selection, factor-decay benchmarking).
- **vinu-initial-analysis** (`initial-analysis-api` :8083) — computes 25
  deterministic "angles" per stock (trend lifecycle, session structure, news
  causality, drawdown/anomaly detection, session correlations). This is the
  context both the risk critic and (as of today) the LLM strategy generator in
  vinu-research consume.

**Aim achieved:** a ticker added to the watchlist gets historical OHLCV + news
backfilled, technical/factor features computed, and deterministic market-structure
analysis produced — automatically, without a human running each stage by hand
(fixed today's-earlier work: this was previously a manual, partially-broken chain).

### 1.3 Strategy layer — two independent, parallel mechanisms

This is the part most worth understanding clearly, because there are **two
separate systems that both produce "target portfolio weights," and they don't
talk to each other**:

**(a) vinu-strategy (`strategy-api` :8084)** — a deterministic, user/AI-authored
**YAML rule engine**. Strategies are YAML files (4 ship today: MA crossover,
RSI mean reversion, ADX-filtered crossover, news-aware momentum) loaded by a
`StrategyRegistry`. A `WeightPipeline` chains four stages: `selection` → `allocation`
→ `timing` (rule-based DSL, produces a `rule_trace`) → `risk` (`max_weight`,
`cash_floor` — per-strategy caps only, not portfolio-level). Inputs: `GET
/features/{symbol}` from vinu-tools, `/impact`, `/correlation`, `/drawdown` from
vinu-initial-analysis. Output: weights written to partitioned Parquet
(`data/weights/{strategy}/{yyyy}/{mm}/{dd}.parquet`) and served over HTTP.
`YAML-REFERENCE.md` in the package is written explicitly so an LLM agent can
author new YAML strategies by reading it as a spec. A `schedule` CLI command
polls per-strategy hourly/daily/weekly/monthly cadences.

**(b) vinu-research (`research-api` :8087)** — generates **Python** `BaseStrategy`
classes (template-based via a recipe library, or, as of today's change,
LLM-generated and LLM-refined every iteration) and runs them through
`vinu-simulator`'s backtest engine in an iterate-critique-refine loop (up to
`max_iterations`, gated by a rule-based + optional LLM-augmented risk critic,
holdout validation, and walk-forward analysis). Approved strategies become
tracked "artifacts" (SQLite-backed) with a decay-monitoring lifecycle
(`CREATED → BENCHING → ACTIVE → MONITORING → DECAYED → DISABLED`), scanned on a
schedule (`vinu-research schedule-decay`).

**vinu-simulator (`simulator-api` :8085)** is the shared backtest engine both (a)
and (b) run through — it fetches YAML-derived weights from vinu-strategy
*or* executes an LLM/template-generated Python strategy directly, and produces
the same `BacktestResult` shape either way. This is the one place the two
mechanisms are unified — at the *measurement* layer, not the *generation* or
*decision* layer.

**Aim achieved:** two independent, fully-wired ways to go from raw market data to
a backtested, evaluated strategy — one fast/deterministic/interpretable (YAML
rules), one adaptive/generative (LLM). Both are real, not stubs; both have
consumers.

### 1.4 Orchestration layer — vinu-agent (`agent-api` :8086)

The chat/tool-calling orchestration layer. Internals beyond the HTTP server:

- **`tools/`** — wraps every upstream service (news, stock-price, features,
  initial-analysis/correlation, strategy, simulator, research) as callable LLM
  tools, plus a `trade_tool.py` for order submission.
- **`session/`** — durable conversation/task state (`Session`, `Message`,
  `Attempt`), SSE event streaming, session search.
- **`memory/`** — flat-file Markdown "remember X" long-term notes (not a vector
  store).
- **`swarm/`** — genuine multi-agent orchestration. 30 pre-built YAML "team"
  presets (`quant_strategy_desk.yaml`, `risk_committee.yaml`,
  `crypto_trading_desk.yaml`, `macro_rates_fx_desk.yaml`, etc.), each a list of
  role/prompt-templated tasks, dispatched via a thread-pool runtime.
  Manually invoked (`vinu-agent swarm run <preset>`), not scheduled.
- **`broker/`** — a real Alpaca integration (paper by default, `ALPACA_PAPER=true`),
  not a message broker. `AlpacaBroker` supports live order submit/cancel/replace.
  Gated by a `TradingMandate` (position/order/volume caps, allowed/blocked
  tickers, `require_confirmation` — defaults **True**), an `OrderGuard`
  pre-trade check, and a filesystem `kill_switch` (halts all trading via a
  sentinel file). By default, `trade_tool.py` does **not** execute an order —
  it returns `pending_confirmation` and waits for a human.
- **`channels/`** — real Telegram/Discord bot code exists (`BaseChannel`
  subclasses) but is **not wired up anywhere**: nothing in `service.py` or
  `server/app.py` starts a bot, and `vinu-agent channel send` explicitly
  returns `"status": "not_implemented"`. This means the human-confirmation
  flow above has no delivery mechanism today — a `pending_confirmation` order
  currently has nowhere to notify a human except the chat session itself.
- **`skills/`** — 20 knowledge-injection prompt packs (risk-analysis,
  execution-model/slippage-VWAP-TWAP, shadow-account trade-journal
  backtesting, factor-research, options-trading, etc.). These are reference
  material the LLM can pull into its reasoning during a chat/swarm run — they
  are not automated pipelines. E.g. `execution-model` documents
  Almgren-Chriss slippage models and TWAP/VWAP slicing logic as *text the LLM
  can read*, not code that executes an order that way.

**Aim achieved:** a single conversational/API surface that can call every
pipeline stage as a tool, run structured multi-agent research workflows, and
(manually, behind explicit gates) place real orders in a paper account. This is
a capable manual/co-pilot trading assistant.

### 1.5 What does not exist: vinu-live

There is no `vinu-live` package anywhere in the repo. It is documented in
`new-direction-for-the-project.md` as "NOT STARTED — next major piece after
agent wiring settles," intended as the eventual production execution layer that
decides, on its own schedule, what to trade based on approved strategies
(YAML or LLM-Python — that handoff format is itself an open decision in that
doc). `vinu-agent`'s `broker/` module is explicitly a stopgap manual-trading
tool, not this.

---

## 2. Aims achieved so far (by stage)

| Stage | Aim | Status |
|---|---|---|
| Data ingestion | Add a ticker → auto-backfill 2023+ OHLCV + news | ✅ automated (fixed this session) |
| Feature/factor compute | Auto-compute indicators/factors for any watchlist ticker | ✅ automated |
| Market structure analysis | Auto-compute 25 deterministic angles per ticker | ✅ automated |
| Deterministic strategy authoring | Human/AI writes YAML rules, gets weights + backtest | ✅ fully wired |
| Generative strategy research | LLM proposes + iteratively refines a strategy against real backtests | ✅ iteration 1 always; iteration 2+ now LLM-driven (fixed this session) |
| Strategy lifecycle | Approved strategy tracked, decay-monitored on a schedule | ✅ wired (this session) |
| Orchestration | One chat/API surface can drive the whole pipeline as tools | ✅ working |
| Manual paper trading | A human, via chat, can approve and place a real (paper) order | ✅ working, gated by mandate + kill switch |
| Autonomous live trading | System decides and executes trades on its own, manages a real portfolio | ❌ does not exist |

---

## 3. Shortcomings — granular gap list

Organized from "closest to done" to "not started at all."

### 3.1 Research loop (vinu-research) — mostly closed, small gaps remain
- **No autonomous hypothesis generation.** `ensure_strategy`/`ensure` still
  require a human-supplied `idea` string. The LLM never looks at a symbol's
  angle context and proposes *what* to research — only *how* to refine an idea
  it's handed. This is the natural next LLM-first target.
- **Decay detection doesn't trigger re-research.** `schedule-decay` flags a
  strategy as DECAYED but nothing automatically calls `ensure_strategy` with a
  fresh idea when that happens — a human still has to notice and re-trigger.
- **`vinu-tools`/features client noted as unused ("dead client") inside
  vinu-research** per the project's own planning doc — configured
  (`DEFAULT_FEATURES_API_URL`) but not actually called from the research loop,
  meaning the rich Alpha101/191/ML feature library isn't reaching the LLM
  generator or template recipes at all today.
- **`--no-llm`/template-only refinement path** is intentionally not being
  developed further right now (explicit decision, documented in code comments
  added this session) — acceptable per current LLM-first strategy, but means
  the system has zero fallback quality if the LLM becomes unavailable in
  production, beyond "revert to iteration-1-only behavior."

### 3.2 Strategy-generation duality (vinu-strategy vs vinu-research)
- **No bridge between the two mechanisms.** YAML rule strategies and
  LLM-Python strategies are backtested through the same simulator but never
  compared, ensembled, or arbitrated against each other. There's no logic
  deciding "use the YAML rule here, the LLM strategy there," or combining
  both into one portfolio decision.
- **`vinu-strategy`'s risk stage is per-strategy only** (`max_weight`,
  `cash_floor`) — there is no cross-strategy, portfolio-level risk logic
  anywhere in either mechanism.
- **Env var mismatch flagged in exploration**: `docker-compose.yml` sets
  `VINU_INITIAL_ANALYSIS_API_URL` for `strategy-api`, but `vinu_strategy/config.py`
  reads `VINU_CORRELATION_API_URL` — worth verifying whether an alias exists;
  if not, `strategy-api` may be silently falling back to its default
  correlation URL rather than the compose-configured one.

### 3.3 Portfolio management — does not exist
- **No capital allocation across strategies.** With N active strategies
  (YAML or LLM-generated), nothing decides how much capital/risk budget each
  gets. No risk-parity, Sharpe-weighting, or correlation-aware allocation
  exists anywhere in the codebase — `risk-analysis` and `execution-model` are
  currently just LLM reference *prompts* (skills), not executable logic.
  A correlation matrix across the *active portfolio's own strategies* (as
  opposed to per-ticker correlation from vinu-initial-analysis) doesn't exist.
- **No position sizing methodology** (Kelly, vol-targeting) implemented as
  code — again, only referenced as prompt knowledge in the `execution-model`
  skill for the LLM to reason about ad hoc in chat, not applied consistently.
- **No portfolio-level drawdown circuit breaker.** The only kill switch is a
  single global filesystem flag (`/tmp/vinu-trading-halt`) — no per-strategy,
  per-symbol, or portfolio-drawdown-triggered automatic halt.

### 3.4 Execution — largely absent
- **Naive order submission only.** `AlpacaBroker.submit_order` places a single
  order; there is no TWAP/VWAP slicing, no slippage-aware execution, despite
  the `execution-model` skill documenting exactly these techniques as
  reference material the LLM could apply but doesn't automatically.
- **No signal → order translation layer.** Nothing converts a strategy's
  target weight series (from either vinu-strategy or vinu-research) into a
  sequence of orders against current broker positions — that translation
  would need to diff target weights vs. actual holdings, size the delta, and
  route it through the order guard. This layer doesn't exist.
- **No reconciliation/accounting layer.** No code compares broker-reported
  positions/fills against internal expected state, so there's no way to
  detect a missed fill, a partial fill, or drift between what the system
  *thinks* it holds and what it *actually* holds.

### 3.5 Continuous/autonomous operation — absent
- **Nothing schedules trading decisions.** Unlike the data pipeline (which is
  fully continuous via compose + internal loops), nothing periodically
  evaluates active strategies' current signals and decides whether to trade —
  `agent-api`'s only compose process is the chat/API server; broker actions
  are 100% manually or LLM-conversation triggered.
- **Human-confirmation flow has no delivery channel.** `require_confirmation`
  defaults to True and blocks execution pending approval, but Telegram/Discord
  bots are unwired — a `pending_confirmation` order has no path to actually
  notify a human outside an active chat session, making unattended operation
  with the safety gate on effectively impossible right now.

### 3.6 Validation before capital promotion — conceptual only
- **`shadow-account` skill** describes exactly the right methodology (extract
  trades → simulate what-if → compare shadow vs actual P&L → identify sizing
  and timing leaks) but is a document the LLM can read, not a pipeline that
  runs automatically before a strategy graduates from paper to live capital.
- **No formal "paper-trade for N days before real capital" gate** — the
  `ArtifactStatus` lifecycle (`BENCHING → ACTIVE`) exists conceptually in
  vinu-research's decay model, but nothing connects that state machine to
  actual paper-trading P&L collected via the broker.

---

## 4. Methodology to close the gap — phased

**Phase A — finish closing the research loop (small, in progress)**
1. Autonomous hypothesis generation: LLM proposes ideas from angle context,
   not just refines a human's idea.
2. Decay → re-research auto-trigger: `schedule-decay` calls `ensure_strategy`
   with a freshly-LLM-proposed idea when a strategy DECAYS, closing the loop
   without human intervention.
3. Wire the vinu-tools feature/factor library (Alpha101/191, ML pipeline)
   into the LLM generator/template recipes so richer signals reach strategy
   authoring, not just the 3 hardcoded indicators used today.

**Phase B — build the missing bridge and portfolio layer**
4. A **portfolio construction service** (new, or a new module in
   vinu-strategy/vinu-agent): takes all ACTIVE artifacts (YAML + LLM-Python),
   computes a correlation matrix across their signals/returns, and allocates
   capital/risk budget per strategy (risk-parity or Sharpe-weighted, with a
   max-per-strategy and max-per-sector cap).
5. Codify position sizing (vol-targeting or fractional-Kelly) as executable
   code, not just an LLM skill reference — applied consistently by the
   portfolio construction service, not ad hoc per chat.
6. Portfolio-level circuit breakers: drawdown-triggered halts (not just a
   manual global kill switch), scoped per-strategy and portfolio-wide.

**Phase C — build vinu-live (the execution engine)**
7. Signal → order translation: diff target portfolio weights against current
   broker positions, size the delta, route through `OrderGuard`.
8. Execution algorithms: implement the slippage/TWAP/VWAP models the
   `execution-model` skill already documents as actual order-slicing code.
9. Scheduling: a continuous process (new compose service) that periodically
   pulls current strategy signals and runs the above — the one piece
   currently missing that would make trading autonomous rather than
   chat-triggered.
10. Reconciliation: compare broker-reported fills/positions against expected
    state after every order cycle; alert on drift.

**Phase D — validation gate before real capital**
11. Automate the shadow-account methodology: after N days/trades of paper
    execution, auto-generate the shadow P&L comparison and require it to clear
    a bar (e.g., paper Sharpe within X% of backtest Sharpe) before a strategy's
    `ArtifactStatus` can move from BENCHING/paper to ACTIVE/real capital.
12. Feed live/paper P&L back into the decay engine so decay detection is
    grounded in real trading results, not just re-backtested historical data.

**Phase E — human oversight, made actually usable**
13. Wire the Telegram/Discord channels so `pending_confirmation` orders
    actually notify a human outside an active chat session — without this,
    the safety gate that's supposed to make autonomous operation acceptable
    doesn't function unattended.
14. Expand the kill switch to per-strategy/per-symbol granularity, and add
    structured audit logging of every order/confirmation/override for
    after-the-fact review.

**Phase F — observability**
15. A dashboard (or agent tool) comparing live/paper positions and P&L against
    each strategy's backtest expectations in real time, so divergence is
    visible before it becomes a large loss — this is the feedback surface
    that makes every phase above trustworthy rather than a black box.

Phases B and C are the largest lift and the actual definition of "self-reliant
with portfolio management on real trading" — everything before that is either
already done or is refining strategy *generation quality*, not *portfolio
execution*, which is the part that doesn't exist yet at all.
