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
- **Angle integration (step 2)**: `format_angle_context_lines()` extracted into `angle_context.py` as a shared renderer; the LLM strategy *generator* prompt (`llm_generator.py::_build_generation_prompt`) now consumes it too, not just the risk critic. `loop.py` fetches angle context once per run (symbol + interval only, not per-iteration) so it's available starting at iteration 1 — previously it was only fetched after code generation, so even the critic's context lagged one iteration behind on effect. Test suite: 352 passed (1 pre-existing flaky sqlite concurrency test unrelated to this change).

- **vinu-agent wiring (2026-07-20)**: `vinu-research` had no HTTP server actually running despite `server/app.py::create_app` existing — added `serve` subcommand (`cli.py`, mirrors `vinu-strategy`'s pattern), `host`/`port` config (`VINU_RESEARCH_HOST`/`_PORT`, default `127.0.0.1:8087`), a `Dockerfile`, and a `research-api` block in `docker-compose.yml` (port 8087 — 8086 was already claimed by `vinu-agent` itself, which the pre-existing `ResearchTool`'s stale default silently collided with). Also fixed `vinu_agent/tools/research_tool.py`, which already existed but sent a payload (`idea`, `interval`) that didn't match the real `/research/run` schema (`user_idea`, no `interval` field) — it would have failed Pydantic validation (422) against the real server the first time anyone tried it. Added `indicators`/`initial_capital`/`universe`/`dry_run` passthrough, fixed the URL default, added a `strategy-research` skill (`vinu-agent/skills/`) documenting the workflow, and 6 new tests. Smoke-tested `serve` + `/health` + `/research/run` (dry_run) end-to-end manually.

### Remaining integration work
- Legacy `/story` shape mismatch: `correlations.by_session` and `baseline_anomalies` expected by the prompt are never populated by the current initial-analysis endpoint. Confirmed structurally impossible today (not just empty) — the fields are a stub for a still-unbuilt spec (`personal-important/project-status/same-but-rewritten/2-what-to-build-and-optimize.md` §2.1: `compute_correlation_by_session()` + baseline-anomaly detection). Currently harmless (guarded, fails safe) but misleading; no action taken yet pending a decision (leave/remove/build).
- Decide Python-code vs strategy-YAML handoff for approved strategies.
- `vinu-live` (paper/live trading execution, case 3 of the 3-component Research-Simulations split: `vinu-research` = researcher, `vinu-simulator` = deterministic backtest engine, `vinu-agent` = orchestration layer) — NOT STARTED, next major piece after agent wiring settles.

### Pipeline plumbing fixes (2026-07-20)
An audit found the ticker→backfill→analysis→strategy pipeline the user described was not actually connected — each stage was a separate manual switch, two of them silently no-op'd, and the artifact/decay lifecycle store had no writer at all. Fixed all seven identified gaps:
1. **Watchlist sync** — `vinu-news`/`vinu-stock-price` `add_watchlist_tickers` now export to the shared `watchlist.json` on add, and their continuous ingest loops now pull from it each cycle (`sync_watchlist_from_shared`, already existed but was never called by anything).
2. **News backfill execution** — `ensure_ticker_backfill` only ever scheduled a pending row; `run_backfill_all()` is now called once per poll cycle inside `vinu-news-ingest`'s loop, so scheduled backfills actually run.
3. **Stock-price backfill trigger** — new `get_pending_backfill_symbols()` (watchlist symbols with no/incomplete catalog `backfill_status`) checked and backfilled once per cycle inside `vinu-stock-ingest`'s loop; previously zero automation existed.
4. **`initial-analysis-compute` no-op** — `docker-compose.yml`'s command had no tickers and no `--all`, so it printed help and exited every restart. Fixed the compose command and moved watchlist resolution *inside* the continuous loop (was fetched once before the loop, so new tickers were never picked up without a restart).
5. **Approve → artifact bridge** — `research_runs` now persists the winning candidate's `strategy_code`; `ResearchService.approve_run` now builds an `Artifact` (ACTIVE, with `strategy_code`/`source_run_id`/`initial_sharpe`/`initial_max_dd`) and an initial `BenchEntry` in `strategy_store.db`. Previously approving a run only flipped a status column — the artifact table had no writer anywhere.
6. **`decay-scan` scheduling + a real bug fix** — new `schedule-decay` CLI command (interval loop, mirrors `vinu-strategy`'s `schedule` pattern). Also found and fixed: `get_snapshots()` returns newest-first, but `decay_scan_main` was appending it un-reversed before the current evaluation, feeding `transition_status` the wrong end of the history. Also found: `evaluate_health()`'s IC/IR scoring is meaningless for single-strategy artifacts (they only ever have `sharpe` in bench history, never real `ic`/`ir`) — would have driven every approved strategy toward DECAYED/DISABLED regardless of actual performance. Added a parallel `evaluate_strategy_health()`/`compute_strategy_decay_snapshot()` path (rolling-Sharpe-vs-baseline only), used for `type == "strategy"` artifacts; factor artifacts keep the original IC/IR path unchanged.
7. **Zero-strategy trigger** — new `ResearchService.ensure_strategy()` / `has_active_strategy()`, exposed as CLI `vinu-research ensure <idea> --symbol SYM` and `POST /research/ensure`: runs research only if the symbol has no ACTIVE/MONITORING artifact yet. Still requires a human-supplied idea (no autonomous hypothesis generation) — that remains a gap, but the "don't re-research a covered ticker" half is now real.

All five affected packages' test suites pass (vinu-news 81, vinu-stock-price 30, vinu-initial-analysis 60, vinu-research 363) with tests added for every new behavior, including regression tests for the two latent bugs found (decay ordering, IC/IR-on-strategy-artifacts).

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
