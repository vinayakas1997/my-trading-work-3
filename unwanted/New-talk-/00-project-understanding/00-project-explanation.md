---
name: project-explanation
status: discussion-phase
purpose: explains the overall vinu project — its three phases, the agent components, and how user input (tickers + strategies) flows through analysis and reporting. Written to capture the project picture so it doesn't need re-explaining.
---

# Vinu Project — Project Explanation

> **Always think from the perspective of stage 1 only.** Never think about
> stage 2 or stage 3. In the stage mapping below, always consider every component
> through the lens of stage-1 pre-analysis.

## The big picture

Vinu is an agentic trading-analysis system. The user gives it a set of **tickers**
and **strategies** (in a defined format), and agents run **full analysis** over a
defined time window, then prepare a **report** — which strategies work, and what
modifications would make them better.

The project is organized around **three phases of understanding**:

1. **a) Full pre-analysis (present project)** — the current focus
2. **b) Full-analysis + new data (live data)** — same analysis with live data,
   accommodating live trading
3. **c) During-trading analysis** — what analyses can be done while trading is live

Today the project is purely on **phase (a) pre-analysis**.

## Phase (a) — Full pre-analysis (the current focus)

### Inputs

- A defined time period: `start_date` → `end_date`
- A set of **tickers**
- A set of **strategies** (provided in a defined format)

### Goals

1. **Accept** a defined input: a time window (`start_date` → `end_date`), a set of
   tickers, and a set of strategies (in the defined format) — without manual
   per-run configuration.
2. **Analyze** the window through all the angles (news, regime, trend, shock,
   performance, ML) — not just a single lens.
3. **Evaluate** each strategy against the window's history: which worked, which
   didn't, with per-angle evidence (not vibes).
4. **Recommend** — concrete modifications that would improve a strategy, each
   traceable to which angle/combination it came from.
5. **Produce a step-by-step report** the user can act on (which strategy, why, and
   what to change).

### What happens

1. `vinu-initial-analysis` runs full analysis over the window, using a set of
   **angles** — each angle is one lens on the information.
2. The analysis produces per-angle outputs (signals, event labels, statistics,
   model predictions).
3. `vinu-agent` prepares a **report** with different steps: which strategy worked,
   whether any modification can make it better.
4. The report uses the information from the angles — and importantly, *in which
   combination* the angles can be used to make the result better.

### The angles (in vinu-initial-analysis)

The news↔price work in this repo is one angle among many:

- `news_price_causality`, `news_first_analysis` — news-related angles
- `ml_model_pipeline` — ML prediction layer
- `backtesting_44_metrics`, `pnl_attribution`, `drawdown_deep_dive` — performance
- `shock_clustering`, `shock_personality` — event/shock structure
- `regime_analysis`, `trend_lifecycle`, `trend_session_structure`, `peer_relative_strength` — regime/trend/relative

The future agent weighs signals from all angles (regime, trend, shock, news,
performance, ML) before any decision — the news angle is one cell of that picture.

## The agent components (vinu-agent)

- **vinu-research** — the research/analysis engine
- **vinu-simulator** — simulates strategies over historical windows
- **vinu-tools** — feature extraction, presets, run registry (OHLCV → features)
- **vinu-agent** — the agent itself:
  - tools: backtest, strategy, stock_price, news, trade_plan, research,
    factor_analysis, portfolio, etc.
  - skills: alpha-zoo, strategy-generate, risk-analysis, sentiment-analysis,
    trade-plan, gatekeepers, live-safety, macro-analysis, etc.
  - session/swarm/workflow orchestration

## Where the news L1–L4 work fits

The news analysis research is an **input improvement to phase (a)**: it makes the
`news_price_causality` angle better by giving it real text features (event type,
entities, etc.) instead of the disproven sentiment score. It improves the raw
material the agent reasons over — one cell in a much bigger picture.

## Stage mapping

The project is split into stages. This section records which components belong
to which stage.

### Stage 1 (pre-analysis) — the components touched

| Component | Role in stage 1 |
|---|---|
| vinu-news | Data layer — news ingestion + L1/L2 analysis features |
| vinu-stock-price | Data layer — historical OHLCV |
| vinu-tools | Feature/indicator computation feeding analysis |
| vinu-initial-analysis | The core — 25 angles running over [start, Qn] |
| vinu-strategy | Strategy YAML + 4-stage pipeline (selection → allocation → timing → risk); replayed & validated by the simulator in stage 1 |
| vinu-simulator | Backtesting strategies over the window |
| vinu-research | The research engine — generates/refines strategies |
| vinu-agent | The report producer — synthesizes the step-by-step report (the Option-A replay-validation angle) |
| vinu-infra | Shared infrastructure (SQLite, debug) — all stages |

### Stage 2 (live trading) — not in stage 1

- **vinu-live** — execution engine (signal→order, TWAP/VWAP, scheduling, reconciliation)
- **vinu-portfolio** — portfolio construction, capital allocation, risk, drawdown
- **vinu-strategy** — the same pipeline, but for live decision-making → target portfolio weights (information-only in stage 1)
- **vinu-news + vinu-stock-price** — used again, but for live data
- **vinu-agent-2** (conceptual) — a *separate* agentic system, distinct from stage-1 vinu-agent: scheduled pre-analysis (e.g. the 1-week window before trading) decides what to go with, then real-money live trading starts

### Stage 3 (during/post-trade) — not in stage 1

- vinu-live (fills, reconciliation) + vinu-portfolio (drawdown monitoring, circuit breakers) + trade-record/analysis

### Resolution (from discussion)

vinu-research, vinu-simulator, and vinu-agent are **confirmed part of stage 1** —
they produce the report. The agentic layer is a sub-phase *within* stage 1.
vinu-strategy is included in stage 1 because the simulator consumes the same YAML
strategy format for replay/validation; it gains its live role only in stage 2.

## Related files

- `../01-news-analysis-methods/` — the news-side research (L1–L4 framework)
- `../02-price-analysis-methods/` — the price-side research (Kronos, TSFM, etc.)
- `differnt-combination-analysis.md` (same folder) — the combination matrix
  (price-alone / news-alone / news+price / price+other-data)
