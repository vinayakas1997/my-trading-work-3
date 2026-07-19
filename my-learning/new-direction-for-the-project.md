# 3-Environment Architecture

## Initial-Analysis · Research-Simulations · Live-Trading

---

## 1. Overview

The system is split into three isolated environments, each with a distinct purpose, data flow, and execution model:

```
Initial-Analysis  ──feeds──>  Research-Simulations  ──approves──>  Live-Trading
  (deterministic)               (LLM-driven)                        (production)
```

**Data flows downhill only:**
- `Initial-Analysis` produces structured angle results (parquet) → consumed by `Research-Simulations` as features/context
- `Research-Simulations` produces candidate strategies → approved strategies flow to `Live-Trading`
- `Live-Trading` produces execution logs → consumed by `Initial-Analysis` for PnL attribution analysis

**Key principle:** Any LLM or non-deterministic component lives exclusively in `Research-Simulations`. `Initial-Analysis` and `Live-Trading` are entirely deterministic — same inputs always produce same outputs.

---

## 2. Initial-Analysis (completed)

**Package:** `vinu-initial-analysis` (renamed from `vinu-correlation`)

### Purpose
Foundational, deterministic analysis that runs for every stock. No LLM involvement. Produces structured angle data consumed by Research-Simulations and stored for querying.

### Scope — 19 Angles

| Category | Angles |
|---|---|
| **News** | news_first_analysis, session_time_analysis, news_price_causality |
| **Technical** | technical_indicators, factor_backtesting |
| **Risk** | drawdown_deep_dive, regime_analysis, deflated_sharpe_ratio, validation_overfitting |
| **Portfolio** | backtesting_44_metrics, benchmark_comparison, portfolio_analysis, pnl_attribution |
| **Statistical** | pairs_cointegration, decay_monitoring, event_study_methodology |
| **Machine Learning** | ml_model_pipeline, shadow_trading |
| **Fundamental** | fundamentals |

Each angle runs at multiple time resolutions (15min, 1H, 1D, 1W, 1M, 6M) — specified in `spec.yaml` via `time_formats`. The runner loops over each format, fetches bars at that granularity, and calls `compute(symbol, bars, news, from_ts, to_ts, time_format)`.

### Architecture

```
vinu-initial-analysis/
├── vinu_initial_analysis/
│   ├── angles/            # 19 self-contained folders
│   ├── runner.py          # Dynamic discovery + execution
│   ├── storage/           # Parquet writer/reader + SQLite run log
│   ├── catalog/           # Auto-generated angles.yaml from spec.yaml
│   ├── cli.py             # run, list-angles, status, serve
│   ├── api.py             # Backward-compat CorrelationAPI
│   ├── service.py         # Facade wrapping runner + storage + clients
│   ├── server/            # FastAPI routes
│   ├── clients/           # News + price data clients
│   └── config.py          # VinuInitialAnalysisConfig
```

### Key Design Decisions

1. **No shared `engine/`** — each angle owns all its code. Deleting an angle folder removes everything with no side effects. Duplication is explicitly fine.
2. **Schema-agnostic storage** — each angle decides its data columns. Storage auto-stamps: `symbol`, `angle_name`, `time_format`, `run_id`, `started_at`, `analysis_from`, `analysis_until`, `stored_at`.
3. **Runner discovers dynamically** — scans `angles/*/compute.py`. Add/remove by folder, no registration needed.
4. **Time-format-aware** — `time_formats` in `spec.yaml` tells the runner what bar resolutions to prepare. One call to `compute()` per time_format, results concatenated and stored as one run.
5. **Backward compatible** — old `vinu-correlation` CLI aliases preserved, `CorrelationAPI` class kept with updated internals.

### What Was Done

| Step | Detail |
|---|---|
| Restructure | `vinu-correlation` → `vinu-initial-analysis`. Moved engine modules into angle folders. |
| Delete aimless | Removed 6 angles that produced no stock analysis (alpha_factor_zoo, expression_dsl, strategy_expressions, rl_training_environment, scheduled_cron_research, research_loop). |
| Time formats | Added `time_formats` to all 19 specs. Runner loops over them, passes bars at each resolution. |
| Wire existing engine | 5 angles with pre-existing code (baseline, impact, correlation, granger, drawdown, event_study, blocks, market_hours, calendar) wired into compute.py. |
| Port mimi-agent scripts | 14 angles ported from what-outcomes/mimi-agent-analysis diagnostic scripts. |
| Data pipeline | Runner receives `price_client` + `news_client`, fetches real bars and articles, passes to compute(). |
| HTTP API | `/angle/{name}/{ticker}`, `/run/{ticker}`, `/angles`, `/symbols` + backward-compat legacy endpoints. |
| Tests | 68 passing, 0 failures. |

### Status: COMPLETE

Ready to feed data to Research-Simulations.

---

## 3. Research-Simulations (exists — integration in progress)

**Package:** `vinu-research` (LLM-driven strategy research)

### Purpose
Takes outputs from Initial-Analysis and uses LLM agents to research, generate, backtest, and refine trading strategies. This is the only environment where LLMs are invoked.

### Audit findings (2026-07-20)
A substantial `vinu-research` package already exists from a prior iteration and is worth reusing, NOT rebuilding:
- The loop in `loop.py` already implements quant coder → backtest → risk critic → refine → approve, with strong anti-overfitting machinery: static AST verification, walk-forward (default on), a true holdout slice with PASS-downgrade on failure, min-30-trades floor, weight-holding verification.
- Strategy-evaluation machinery (decay, benchmark, walk-forward, comparison) already lives here — confirming the Initial-Analysis angle trim: `decay_monitoring`, `benchmark_comparison`, `validation_overfitting`, `backtesting_44_metrics`, `factor_backtesting`, `ml_model_pipeline`, `shadow_trading`, `portfolio_analysis` are earmarked for removal from vinu-initial-analysis (their job belongs here, applied to strategies, not raw stocks). Keep in Initial-Analysis: trend_lifecycle, trend_session_structure, news_first_analysis, news_price_causality (+ regime_analysis recommended; technical_indicators / event_study_methodology / fundamentals / pairs_cointegration borderline; pnl_attribution dormant until Live-Trading).
- Consumes services over HTTP: stock-price :8081, features :8082 (dead client, unused), initial-analysis :8083 (legacy `/story` `/drawdown` `/correlation` endpoints), simulator :8085. LLM is provider-agnostic (OpenAI-compatible base URL, default local Ollama, off by default).
- `vinu-strategy` (YAML strategy engine + web UI) is standalone — the natural "approved strategy" representation for Live-Trading. Open design decision: research emits Python strategy code today; the approve→live handoff (Python vs YAML) must be decided before Live-Trading.

### Fixed 2026-07-20
- Windows portability: removed Unix-only `fcntl` lock in `hypothesis_registry.py` (lock was on a private temp file — atomicity comes from `os.replace`). Unblocked 7 test modules.
- `sqlite_backend.py`: newest-first ordering tie-break (`ORDER BY created_at DESC, id DESC`) and monotonic `updated_at` on coarse clocks.
- **Angle integration (step 1)**: new `angle_context.py` compacts `/angle/{name}/{ticker}` output (latest run, time-format filtered, NaN-cleaned) from `trend_lifecycle`, `trend_session_structure`, `news_price_causality` into `story["angles"]`; the rule-based risk critic and the LLM risk-critic prompt now consume it (suggestions only — verdicts unchanged). Test suite: 349 passed on Windows.

### Remaining integration work
- LLM strategy *generator* prompt (`llm_generator.py`) does not yet receive angle context — only the risk critic does.
- Legacy `/story` shape mismatch: `correlations.by_session` and `baseline_anomalies` expected by the prompt are never populated by the current initial-analysis endpoint.
- Decide Python-code vs strategy-YAML handoff for approved strategies.

### Key Design Principle
All strategies produced here must be fully deterministic when replayed. The LLM is used for *generation* and *refinement*, not for live decision-making. Once a strategy is approved, it becomes a static config consumed by Live-Trading.

### Status: EXISTS (prior iteration) — angle integration started 2026-07-20

---

## 4. Live-Trading (future)

**Package:** `vinu-live` (production execution)

### Purpose
Production execution of approved strategies. Deterministic, no LLM at runtime. Reads approved strategy configs from Research-Simulations and executes them against real broker APIs.

### Planned Scope
- Broker integration (Alpaca, IBKR)
- Order execution engine (market, limit, stop)
- Position sizing and portfolio allocation
- Real-time risk limits and circuit breakers
- Execution log → feeds back to Initial-Analysis for PnL attribution

### Key Design Principle
Zero LLM calls during market hours. Every decision is a deterministic function of (strategy_config, market_data). If a strategy needs adjustment, it goes back through Research-Simulations.

### Status: NOT STARTED

---

## 5. What We Did So Far (Timeline)

1. **Package rename**: `vinu-features` → `vinu-tools`. Restructured into `compute/{formulas, bench, ml, factors}` with 499/499 params wired, YAML catalogs, concept index.
2. **Correlation restructure**: `vinu-correlation` → `vinu-initial-analysis`. Dynamic angle discovery, time-format-aware runner, schema-agnostic parquet storage, 19 angles with real logic.
3. **Data pipeline**: Runner receives real price + news clients, loops over time formats, passes data to each angle's compute().
4. **API layer**: FastAPI routes for all 19 angles + backward compat for old CorrelationAPI consumers.
5. **Web UI removed**: Deleted old React dashboard — will be rebuilt fresh.
6. **trend_lifecycle overhaul + trend_session_structure** (2026-07-19/20): fixed ATR threshold inversion, outcome-maturity recapture, walk-forward KNN matching with session soft-filter; added the session-structure angle (16 angles total).
7. **vinu-research audit + integration start** (2026-07-20): reuse-not-rebuild verdict; Windows portability fixed (349 tests green); risk critic + LLM prompt now consume trend_lifecycle / session-structure / news-causality angle context via `story["angles"]`.
8. **Next**: feed angle context into the LLM strategy generator; run the loop end-to-end against real angle data; decide the Python-vs-YAML approved-strategy handoff.
