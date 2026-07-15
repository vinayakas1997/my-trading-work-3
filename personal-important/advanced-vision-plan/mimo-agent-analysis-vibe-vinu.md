# Feature-by-Feature Analysis: Vibe-Trading vs vinu-components

## What vinu-components Does Better (Keep These)

| Pattern | Why It's Good |
|---------|---------------|
| **`ResilientClient` + Circuit Breaker** | Three-layer resilience (circuit breaker, retry, fallback) is production-grade. Vibe-Trading has zero HTTP resilience. |
| **Pluggable Cost Models** (`AlmgrenChrissCostModel`, `FlatCostModel`) | Clean interface swap without touching simulator. Vibe-Trading bakes costs into the engine. |
| **Pluggable Position Sizers** (vol-target, Kelly, fixed) | `build_position_sizer()` factory is a clean extension point. |
| **True Holdout Split** (`_split_research_and_holdout()`) | Genuine OOS validation — the refinement loop never sees holdout data. Vibe-Trading has no holdout concept. |
| **Walk-Forward Analysis** (`WindowSplitter`, `deflated_sharpe_ratio()`) | Systematic walk-forward validation with deflated Sharpe. Vibe-Trading lacks this. |
| **Risk-Free Rate + Skewness/Kurtosis** in metrics | Proper Sharpe/Sortino with risk-free rate; higher-moment stats. Vibe-Trading assumes zero risk-free rate. |
| **Volume-Aware Slippage** | Uses real volume data for execution modeling. |
| **Pluggable LLM Injection** for testing | `quant_coder` and `risk_critic` as callable params — trivially testable. |

---

# Advanced Features to Steal from Vibe-Trading

---

## FEATURE 1: Strategy Development Manager (SDM) — Strategy Lifecycle Management

### What It Is
A system that treats trading strategies as first-class objects with a **health lifecycle**: `CREATED → BENCHING → ACTIVE → MONITORING → DECAYED → DISABLED`. Each strategy is tracked, benchmarked over time, and automatically demoted when its performance decays.

### The Concept (Analogy)
Think of it like a **doctor monitoring a patient**. When a strategy is "born" (registered), it starts as ACTIVE. A定期 health check (decay scan) measures its IC (information coefficient), IR (information ratio), IC-positive ratio, and Sharpe. If 3 consecutive checks are "WARNING", it moves to MONITORING. If it keeps degrading, it's DECAYED then DISABLED. If it recovers (1 HEALTHY reading), it goes back to ACTIVE. This prevents capital from flowing into strategies that stopped working.

### Why vinu-components Needs This
Today vinu-research generates strategies but has **no lifecycle tracking**. Once a strategy is saved, nobody knows if it's still working. The Part 2 plan mentions "decay monitoring" in the SDM context — this is the implementation.

### What Needs to Be Built

| Component | What | Files to Create |
|-----------|------|-----------------|
| `Artifact` model | Dataclass with `id`, `type` (FACTOR/STRATEGY), `name`, `universe`, `status`, `decay_horizon`, `signal_definition`, `entry_rules`, `exit_rules` | `vinu-research/vinu_research/models.py` (extend existing) |
| `ArtifactStatus` enum | `CREATED → BENCHING → ACTIVE → MONITORING → DECAYED → DISABLED` | `vinu-research/vinu_research/models.py` |
| `DecayThresholds` | Configurable thresholds: IC ratio 0.7/0.5/0.3, IR 1.0/0.5/0.1, IC-positive 0.55/0.45/0.35, Sharpe 1.0/0.5/0.0 | `vinu-research/vinu_research/config.py` |
| `DecayEvaluator` | Pure-logic state machine: 3 consecutive WARNING-or-worse → MONITORING; 2 consecutive DECAYED → DECAYED; 3 consecutive CRITICAL → DISABLED; 1 HEALTHY → back to ACTIVE | `vinu-research/vinu_research/decay.py` (new) |
| `DecayMetrics` | Compute rolling IC, IR, IC-positive ratio, Sharpe from bench history; baseline = first 5 entries | `vinu-research/vinu_research/metrics.py` (new) |
| `SqliteStrategyStore` | SQLite with `artifacts`, `bench_history`, `decay_snapshots` tables; WAL mode; FK constraints; `PRAGMA user_version` migrations | `vinu-research/vinu_research/storage/strategy_store.py` (new) |
| `decay_scan` CLI | Periodic scan that loads all ACTIVE/MONITORING artifacts, evaluates decay, transitions states | `vinu-research/vinu_research/cli.py` (extend) |

### State Transition Rules
```
ACTIVE  --(3 consecutive WARNING-or-worse)--> MONITORING
MONITORING --(1 HEALTHY reading)--> ACTIVE
MONITORING --(2 consecutive DECAYED-or-worse)--> DECAYED
DECAYED --(3 consecutive CRITICAL readings)--> DISABLED
```

### Metrics Evaluated Per Check
- **IC ratio** = rolling_IC / baseline_IC (baseline = first 5 bench entries)
- **Rolling IR** = IC_mean / IC_std over rolling window
- **IC positive ratio** = fraction of periods with IC > 0
- **Rolling Sharpe** = annualized Sharpe over rolling window

---

## FEATURE 2: Research Autopilot — Hypothesis-to-Backtest Pipeline

### What It Is
A 4-step tool sequence that turns a research hypothesis into backtest evidence: (1) create a Goal from the hypothesis, (2) generate a backtest config.json, (3) scaffold a SignalEngine stub, (4) link the backtest results back to the hypothesis.

### The Concept (Analogy)
Like a **scientific method enforcer**. You state your hypothesis ("momentum works in A-shares during high-volatility regimes"). The autopilot forces you through: write it down → design the experiment → run the experiment → record the results. No skipping steps. The hypothesis registry is your lab notebook.

### Why vinu-components Needs This
Today vinu-research's loop is linear: idea → generate → backtest → critique → iterate. There's **no hypothesis tracking** — if you run 10 research sessions, you can't compare which hypotheses were validated vs rejected. The autopilot creates an auditable chain from idea to evidence.

### What Needs to Be Built

| Component | What | Files to Create |
|-----------|------|-----------------|
| `Hypothesis` model | `hypothesis_id`, `title`, `thesis`, `status` (exploring/testing/validated/rejected/monitoring), `universe`, `signal_definition`, `run_cards` (linked backtest artifacts) | `vinu-research/vinu_research/models.py` |
| `HypothesisRegistry` | JSON-backed store at `~/.vinu/hypotheses.json`; atomic writes; CRUD + `link_backtest()` + tokenized search | `vinu-research/vinu_research/hypothesis_registry.py` (new) |
| `Goal` model | Research goal linked to a hypothesis; has `objective`, `criteria`, `status` | `vinu-research/vinu_research/models.py` |
| `RunResearchAutopilotTool` | Takes `hypothesis_id`, creates a Goal with embedded hypothesis text | `vinu-research/vinu_research/tools.py` (extend) |
| `GenerateBacktestConfigTool` | Takes `hypothesis_id` + dates, resolves universe codes, writes `config.json` to deterministic run dir | `vinu-research/vinu_research/tools.py` (extend) |
| `ScaffoldSignalEngineTool` | Writes contract-correct `signal_engine.py` stub with hypothesis's signal_definition as docstring | `vinu-research/vinu_research/tools.py` (extend) |
| `LinkAutopilotBacktestTool` | Reads `run_card.json` from completed backtest, calls `HypothesisRegistry.link_backtest()` | `vinu-research/vinu_research/tools.py` (extend) |

### Workflow
```
1. User creates hypothesis: "Momentum decays in low-vol regimes"
   → HypothesisRegistry.create(title, thesis, universe="AAPL")

2. Agent calls RunResearchAutopilotTool(hypothesis_id="hyp_abc123")
   → Creates Goal with objective: "Test momentum decay hypothesis"
   → Returns goal snapshot + hypothesis summary

3. Agent calls GenerateBacktestConfigTool(hypothesis_id, start, end)
   → Writes config.json to ~/.vinu/runs/autopilot_abc123/
   → Returns config path

4. Agent writes signal_engine.py (fills in real logic)

5. Agent calls backtest tool → runs backtest

6. Agent calls LinkAutopilotBacktestTool(hypothesis_id, run_dir)
   → Reads run_card.json, links metrics to hypothesis
   → Hypothesis.status = "testing"
```

---

## FEATURE 3: Alpha Zoo — Factor Registry with AST-Scan Registration

### What It Is
A library of 460+ pre-built alpha factors (from 5 academic sources: qlib158, alpha101, gtja191, academic, fundamental). Each alpha is a standalone Python file with a `__alpha_meta__` dict that gets **statically parsed via AST** (no code execution) for safe registration.

### The Concept (Analogy)
Like a **chemistry reagent catalog**. Each alpha factor is a reagent with a label (`__alpha_meta__`): what it measures (momentum, reversal, etc.), what data it needs (`columns_required`), what markets it works on (`universe`), and how long its signal decays (`decay_horizon`). You browse the catalog, pick reagents, and the system tells you which ones are still "alive" (IC > 0.02, |t| > 2) vs "dead" vs "reversed".

### Why vinu-components Needs This
vinu-features has 23 named indicators + Alpha101/158/360 recipe packs, but:
1. No **lifecycle tracking** — indicators don't know if they're still predictive
2. No **AST-safe registration** — current `feature_catalog.py` doesn't validate metadata
3. No **bench pipeline** — no way to evaluate which indicators are actually useful
4. No **19 specialized operators** — the `rank`, `zscore`, `ts_rank`, `decay_linear` etc. operators from Vibe-Trading are missing

### What Needs to Be Built

| Component | What | Files to Create |
|-----------|------|-----------------|
| 19 Alpha Operators | `rank`, `zscore`, `scale`, `ts_rank`, `ts_corr`, `ts_cov`, `ts_mean`, `ts_std`, `ts_max`, `ts_min`, `ts_argmax`, `ts_argmin`, `delta`, `decay_linear`, `signed_power`, `safe_div`, `vwap`, `cs_rank` — all operating on wide DataFrames (index=date, columns=instrument) | `vinu-features/vinu_features/compute/operators.py` (new) |
| `AlphaMeta` pydantic model | `id` (regex-validated), `theme` (11 allowed values), `formula_latex`, `columns_required`, `universe`, `frequency`, `decay_horizon`, `min_warmup_bars` | `vinu-features/vinu_features/compute/alpha_meta.py` (new) |
| AST-scan registry | `Registry._scan()` walks `.py` files, `ast.parse()`, finds `__alpha_meta__` Assign, `ast.literal_eval()` for safe extraction | `vinu-features/vinu_features/compute/alpha_registry.py` (new) |
| Alpha bench runner | `run_bench()`: loads universe panel + forward returns, evaluates every alpha in parallel (ProcessPoolExecutor), categorizes as alive/reversed/dead | `vinu-features/vinu_features/compute/alpha_bench.py` (new) |
| Alpha compare runner | `run_bench(only=[...])`: evaluates only requested alphas, ranks by IC/IR/IC-positive | `vinu-features/vinu_features/compute/alpha_compare.py` (new) |
| Integration with ML pipeline | Feed alpha bench results into `select_best()` from Phase 1 — automatically select the best alpha for ML scoring | `vinu-features/vinu_features/compute/ml_models/registry.py` (extend) |

### Key Operators to Implement (Priority Order)
1. **`rank(df)`** — Cross-sectional percentile rank per row (most commonly used)
2. **`ts_rank(df, n)`** — Rolling rank (vectorized with `sliding_window_view` for 45x speedup)
3. **`ts_corr(x, y, n)`** — Rolling Pearson correlation
4. **`delta(df, d)`** — First difference at lag d (enforces d>=1 to prevent lookahead)
5. **`decay_linear(df, n)`** — Linear decay-weighted MA (vectorized with einsum for 40x speedup)
6. **`ts_argmax(df, n)`** — Rolling argmax (bottleneck-accelerated for 350x speedup)

### Alpha Categorization Rules
```
alive:    ic_mean > 0.02 AND ic_positive_ratio >= 0.55 AND |t-stat| > 2
reversed: ic_mean < -0.02 AND |t-stat| > 2
dead:     everything else
```

---

## FEATURE 4: Multi-Layer Post-Backtest Attribution

### What It Is
After every backtest, 4 independent attribution layers analyze the strategy's performance: (1) trade-level winners/losers by symbol and exit reason, (2) beta regression vs benchmark, (3) market regime analysis (bull/bear/high-vol/sideways), (4) Monte Carlo permutation test.

### The Concept (Analogy)
Like a **car crash investigation**. Layer 1 says "the left front took the hit" (which trades lost). Layer 2 says "you were driving 20mph faster than traffic" (beta vs benchmark). Layer 3 says "it was raining" (market regime). Layer 4 says "this crash pattern is 95% unlikely to happen by random chance" (statistical significance). Together they tell you whether your strategy's performance is real skill or luck.

### Why vinu-components Needs This
This directly maps to **Phase 4 of Part 2** (post-hoc news/trade attribution). The plan says: "For each trade, query vinu-correlation for articles around the trade timestamp, classify, aggregate win/loss by news type." The multi-layer approach adds beta regression and regime analysis on top.

### What Needs to Be Built

| Layer | What | Files to Create/Extend |
|-------|------|----------------------|
| **Layer 1: Trade Attribution** | `by_symbol_stats()` — per-symbol count, win_rate, total_pnl, avg_pnl; `by_exit_reason_stats()` — per-exit-reason count, total_pnl | `vinu-simulator/vinu_simulator/engine/metrics.py` (extend) |
| **Layer 2: Beta Regression** | OLS regression of strategy returns vs benchmark returns; compute alpha (intercept), beta (slope), R², information ratio | `vinu-simulator/vinu_simulator/engine/attribution.py` (new) |
| **Layer 3: Regime Analysis** | Classify each bar into regimes (bull/bear/high-vol/sideways); compute strategy performance per regime | `vinu-simulator/vinu_simulator/engine/regime.py` (new) |
| **Layer 4: Monte Carlo Permutation** | Shuffle trade PnL order 1000 times; compute Sharpe distribution under null; p-value = fraction with Sharpe >= actual | `vinu-simulator/vinu_simulator/engine/validation.py` (new) |
| **Layer 5: News Attribution** (Phase 4) | For each trade, query vinu-correlation for articles ±6h; classify by news type; aggregate win/loss by type | `vinu-research/vinu_research/attribution.py` (new) |

### Monte Carlo Permutation Test (Detail)
```
Input: actual_sharpe, list of trade PnLs
For i in 1..1000:
    shuffled_pnl = random.shuffle(trade_pnl)
    equity_from_shuffled = cumsum(shuffled_pnl)
    sim_sharpe[i] = compute_sharpe(equity_from_shuffled)
p_value = fraction(sim_sharpe >= actual_sharpe)
Result: actual_sharpe, p_value, sim_mean, sim_std, sim_p5, sim_p95
Minimum: 3 trades required
```

### Beta Regression (Detail)
```
strategy_returns = daily_returns from equity curve
benchmark_returns = from benchmark data
OLS: strategy_returns = alpha + beta * benchmark_returns + epsilon
alpha = Jensen's alpha (excess return unexplained by market)
beta = market exposure (1.0 = full market correlation)
R² = fraction of variance explained by market
information_ratio = mean(excess_return) / std(excess_return)
```

---

## FEATURE 5: Validation System — Monte Carlo + Bootstrap + Walk-Forward

### What It Is
Three independent statistical validation approaches that answer different questions about a backtest's reliability.

### The Concept (Analogy)
Like **three independent auditors** examining the same financial statement:
- **Auditor 1 (Monte Carlo)**: "If these trade results were randomly shuffled, would the Sharpe still look this good?" → Tests if ordering matters
- **Auditor 2 (Bootstrap)**: "If we resampled these daily returns with replacement 1000 times, how wide is the Sharpe confidence interval?" → Tests stability
- **Auditor 3 (Walk-Forward)**: "If we split the backtest into 5 time windows, is performance consistent across all of them?" → Tests consistency

### Why vinu-components Needs This
vinu-research has walk-forward analysis (`WindowSplitter`, `deflated_sharpe_ratio`) but **lacks Monte Carlo and Bootstrap**. These are cheap to add and significantly strengthen the PASS/REFINE/STOP verdict in the research loop.

### What Needs to Be Built

| Tool | What | Minimum Requirements |
|------|------|---------------------|
| **Monte Carlo Permutation** | Shuffle trade PnL order, compute Sharpe 1000x, return p-value | 3 trades minimum |
| **Bootstrap Sharpe CI** | Resample daily returns with replacement, compute Sharpe 1000x, return 95% CI | 5 return observations minimum |
| **Walk-Forward (enhanced)** | Split equity into N sequential windows, compute per-window metrics, return consistency stats | N*2 bars minimum |

### Integration Point
These should be called automatically after every backtest in vinu-simulator when validation config is present, and their results should be included in run cards and fed to the Risk Critic in vinu-research.

### Walk-Forward Consistency Metrics
```
profitable_windows: count of windows with positive return
consistency_rate: profitable_windows / total_windows
return_mean, return_std: mean and std of per-window returns
sharpe_mean, sharpe_std: mean and std of per-window Sharpes
```

---

## FEATURE 6: Shadow Account — Digital Twin for Traders

### What It Is
A system that reverse-engineers a trader's rules from their broker export (CSV/Excel), creates a "shadow profile" of their trading style, generates a backtestable signal engine from those rules, and produces a PnL attribution report showing exactly where their actual performance diverged from their extracted edge.

### The Concept (Analogy)
Like a **DNA analysis of a trader's style**. You take their trade history (broker export), extract their "genetic code" (entry rules, exit rules, holding periods, preferred markets), clone it into a backtestable strategy, and compare the clone's performance to the original. The difference reveals: "You made money on your momentum entries but lost money by holding too long" or "You overtrade in sideways markets."

### Why vinu-components Needs This
This is a **premium feature** that creates enormous user value. If a user has Alpaca trade history (which vinu-stock-price already supports), they could upload it and get:
1. Extracted rules (KMeans clustering of profitable roundtrips)
2. A backtestable strategy
3. Attribution showing their edge and leaks

### What Needs to Be Built

| Component | What | Files to Create |
|-----------|------|-----------------|
| `ShadowRule` model | `rule_id`, `human_text`, `entry_condition` (dict with feature bounds), `exit_condition`, `holding_days_range`, `weight` | `vinu-research/vinu_research/shadow/models.py` (new) |
| `ShadowProfile` model | `shadow_id`, `journal_hash` (SHA1 for idempotency), `rules` (3-5 rules), `profile_text`, `preferred_markets` | `vinu-research/vinu_research/shadow/models.py` |
| `ShadowExtractor` | Parse broker journal → FIFO pair trades → filter profitable → compute features (holding_days, pnl_pct, entry_hour, entry_weekday, RSI, prior_return) → KMeans clustering (auto-k via silhouette) → per-cluster rule extraction | `vinu-research/vinu_research/shadow/extractor.py` (new) |
| `ShadowCodegen` | Jinja2 template → `signal_engine.py` with flattened rule contexts; validates via `ast.parse` + shape check | `vinu-research/vinu_research/shadow/codegen.py` (new) |
| `ShadowBacktester` | Selects liquid baskets per market, renders run_dir, calls vinu-simulator, parses artifacts | `vinu-research/vinu_research/shadow/backtester.py` (new) |
| `ShadowAttribution` | Arithmetic PnL decomposition: noise_trades_pnl, early_exit_pnl, late_exit_pnl, overtrading_pnl | `vinu-research/vinu_research/shadow/attribution.py` (new) |
| `ShadowReporter` | 8-section HTML report with matplotlib charts (equity curve, per-market Sharpe, attribution waterfall) | `vinu-research/vinu_research/shadow/reporter.py` (new) |
| JSON persistence | `~/.vinu/shadow_accounts/{shadow_id}.json`, idempotent via `journal_hash` | `vinu-research/vinu_research/shadow/storage.py` (new) |

### Extraction Pipeline
```
1. Parse broker journal → DataFrame[entry_date, exit_date, symbol, pnl_pct, ...]
2. FIFO pair trades (long entries matched to exits)
3. Filter to profitable roundtrips (pnl > 0), require >= 5
4. Compute features per roundtrip:
   - holding_days, pnl_pct, entry_hour, entry_weekday, market
   - entry_rsi14 (fetched as-of buy_dt via vinu-stock-price)
   - prior_5d_return (fetched as-of buy_dt)
5. KMeans clustering with auto k (2-5) via silhouette score
6. Per-cluster rule extraction using p10-p90 quantile bounds
7. Deduplication by (market, holding_days_range)
```

---

## FEATURE 7: Data Loader Fallback Chains

### What It Is
An ordered list of data sources per market type, tried sequentially until one succeeds. Ensures backtests work across markets even when specific data sources fail.

### The Concept (Analogy)
Like a **travel adapter chain**. You're going to Japan but your US plug doesn't fit. You try: (1) direct plug → fails, (2) universal adapter → works. The fallback chain is the same: try the best source first, fall through to alternatives. The chain ordering balances data quality, rate limits, and API availability.

### Why vinu-components Needs This
Today vinu-stock-price has Alpaca and Polygon as providers. If Alpaca fails (which it did — Bug #2), the entire pipeline stops. A fallback chain would try Polygon, then yfinance, then local CSV.

### What Needs to Be Built

| Component | What | Files to Create/Extend |
|-----------|------|----------------------|
| `FALLBACK_CHAINS` dict | Market → ordered source list | `vinu-stock-price/vinu_stock/providers/registry.py` (extend) |
| `resolve_loader(market)` | Walk chain, return first available | `vinu-stock-price/vinu_stock/providers/registry.py` (extend) |
| `DataLoader` protocol | `name`, `markets`, `requires_auth`, `is_available()`, `fetch()` | `vinu-stock-price/vinu_stock/providers/base.py` (new) |
| `@register` decorator | Self-registration on import | `vinu-stock-price/vinu_stock/providers/registry.py` (new) |
| `VALID_SOURCES` set | Single source of truth for config validation | `vinu-stock-price/vinu_stock/providers/registry.py` (new) |

### Fallback Chain Design
```python
FALLBACK_CHAINS = {
    "us_equity": ["alpaca", "polygon", "yfinance", "stooq", "eastmoney", "local"],
    "crypto":    ["alpaca", "ccxt", "yfinance", "local"],
    "a_share":   ["eastmoney", "akshare", "tushare", "local"],
}
# Ordering: public/unauthenticated first (lower ban risk), key-gated last, local always last
```

---

## FEATURE 8: Provider Capability Layer — LLM Quirk Handling

### What It Is
A data-driven adapter layer that handles per-LLM-provider quirks: reasoning content capture, temperature limits, thought signature round-tripping, and custom headers.

### The Concept (Analogy)
Like a **universal power supply** that automatically detects the device's voltage requirement and adjusts. DeepSeek wants `reasoning_content` in responses, Kimi requires `temperature=1.0`, Gemini has `thought_signature` dict round-tripping. The capability layer makes these transparent to the rest of the application.

### Why vinu-components Needs This
vinu-research uses a local model (`qwen36-35B @ localhost:8009`) via `ResearchLlmClient`. If it ever connects to cloud providers (OpenAI, Anthropic, DeepSeek), each has different quirks. Building this layer now prevents the "it works locally but breaks on cloud" problem.

### What Needs to Be Built

| Component | What | Files to Create |
|-----------|------|-----------------|
| `ProviderCapabilities` frozen dataclass | `name`, `capture_reasoning`, `send_reasoning_content`, `temperature_override`, `normalize_assistant_content`, `default_headers` | `vinu-research/vinu_research/llm/capabilities.py` (new) |
| Provider registry | 17+ providers with specific quirks | `vinu-research/vinu_research/llm/providers.json` (new) |
| `ChatLLM` wrapper | Extends base LLM client with capability-aware request/response transformation | `vinu-research/vinu_research/llm/client.py` (new) |
| Env resolution | Map provider-specific env vars to base URL/key format | `vinu-research/vinu_research/llm/env.py` (new) |

---

## FEATURE 9: Scheduled Research — Background Periodic Jobs

### What It Is
A background executor that runs research jobs on a schedule (interval or cron), survives process restarts via persistent JSON store, and handles stale state from crashed executors.

### The Concept (Analogy)
Like a **cron job manager** but for research. You set up: "Every Monday at 9am, re-run the momentum hypothesis against new AAPL data." The executor polls every 60 seconds, finds due jobs, runs them, advances the schedule. If the process crashes mid-run, the job's status is reset from RUNNING to PENDING on restart.

### Why vinu-components Needs This
Part 2's Phase 2 (session as a feature) and Phase 3 (news as a feature) need periodic re-evaluation. Scheduled research enables: "Every day, check if the news-fusion strategy still outperforms the baseline."

### What Needs to Be Built

| Component | What | Files to Create |
|-----------|------|-----------------|
| `ScheduledResearchJob` model | `id`, `prompt`, `schedule` (interval-ms or cron), `next_run_at`, `status` (PENDING/RUNNING/COMPLETED/FAILED/CANCELLED) | `vinu-research/vinu_research/scheduled/models.py` (new) |
| `ScheduledResearchExecutor` | Background asyncio task polling every 60s; `tick()` finds due jobs, `dispatch()` runs them, `next_due()` advances schedule | `vinu-research/vinu_research/scheduled/executor.py` (new) |
| `ScheduledResearchJobStore` | JSON file at `~/.vinu/scheduled_research/jobs.json`; atomic writes (temp→fsync→replace); schema version envelope | `vinu-research/vinu_research/scheduled/store.py` (new) |
| `recover_stale_running()` | Resets jobs left RUNNING by previous process | `vinu-research/vinu_research/scheduled/executor.py` |
| Cron parser | 5-field cron (minute hour day month weekday) with `*` and `*/n` support | `vinu-research/vinu_research/scheduled/cron.py` (new) |

---

## FEATURE 10: Run Cards — Reproducible Backtest Records

### What It Is
A JSON + Markdown record of every backtest containing: config hash, strategy hash, metrics, artifacts list with SHA256 hashes, validation results, and warnings. Enables reproducibility and auditability.

### The Concept (Analogy)
Like a **flight recorder** for backtests. Every backtest produces a "black box" recording: exactly what code ran, what config was used, what data was consumed, and what results came out. If someone questions your Sharpe ratio, you can prove it by replaying from the exact same hashes.

### Why vinu-components Needs This
Today vinu-simulator saves results (equity curves, trades) but doesn't include **reproducibility hashes** or **config snapshots**. Run cards make every backtest auditable.

### What Needs to Be Built

| Component | What | Files to Create |
|-----------|------|-----------------|
| `write_run_card()` | Compute SHA256 of config.json + signal_engine.py; extract scalar metrics; list artifacts with sizes and hashes | `vinu-simulator/vinu_simulator/engine/run_card.py` (new) |
| `run_card.json` | Schema-versioned JSON with reproducibility, metrics, artifacts, validation | Output format |
| `run_card.md` | Markdown rendering for human readability | Output format |
| Integration | Called automatically at end of every `WeightSimulator.run()` and `simulate_custom()` | `vinu-simulator/vinu_simulator/service.py` (extend) |

### Run Card Schema
```json
{
  "schema_version": "0.1",
  "generated_at": "2026-07-15T10:30:00Z",
  "run_dir": "~/.vinu/runs/run_abc123",
  "backtest": {
    "codes": ["AAPL"],
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "interval": "1D",
    "initial_cash": 100000
  },
  "reproducibility": {
    "config_hash": "sha256:abc123...",
    "strategy_hash": "sha256:def456..."
  },
  "metrics": {
    "sharpe": 1.23,
    "max_drawdown": -0.08,
    "total_return": 0.15
  },
  "artifacts": [
    {"path": "config.json", "size_bytes": 512, "sha256": "..."},
    {"path": "trades.csv", "size_bytes": 10240, "sha256": "..."}
  ]
}
```

---

## FEATURE 11: Security Hardening — Prompt Injection + SSRF Defense

### What It Is
Multi-layer security: (1) prompt injection scanner that detects 5 attack patterns in external text, (2) SSRF prevention for network requests, (3) workspace path containment, (4) AST validation for generated code.

### The Concept (Analogy)
Like a **building security system** with multiple layers: (1) metal detector at entrance (prompt injection scanner), (2) locked doors with key cards (SSRF prevention), (3) security cameras (path containment), (4) structural inspection (AST validation). No single layer is enough; together they're robust.

### Why vinu-components Needs This
vinu-research executes **LLM-generated code** (strategies). If a malicious LLM generates code that exfiltrates data or runs subprocess commands, there's no defense. The AST validation layer from Vibe-Trading blocks: `import subprocess`, `eval()`, `exec()`, `os.system()`, `requests.get()` in generated code.

### What Needs to Be Built

| Component | What | Files to Create |
|-----------|------|-----------------|
| `InjectionRule` models | 5 regex patterns: instruction_override, system_prompt_exfiltration, role_or_channel_claim, secret_exfiltration, tool_abuse | `vinu-lib/vinu_lib/security/scanner.py` (new) |
| `scan_prompt_injection(text)` | Scan untrusted text, return findings with severity + rule_id + excerpt | `vinu-lib/vinu_lib/security/scanner.py` |
| `with_security_warnings(payload, fields)` | Attach warnings to JSON payloads by scanning selected fields; never drops content | `vinu-lib/vinu_lib/security/scanner.py` |
| AST validation for strategies | Check generated `signal_engine.py` for forbidden imports/calls before execution | `vinu-simulator/vinu_simulator/engine/ast_guard.py` (new) |
| SSRF guard | Validate URL targets before fetching (reject CGNAT/mesh/non-global IPs) | `vinu-lib/vinu_lib/security/network.py` (new) |

---

## FEATURE 12: IM Channel Runtime — Multi-Platform Messaging

### What It Is
A unified message bus that decouples the agent from chat platforms. 16 adapters (Telegram, Discord, Slack, WhatsApp, etc.) share the same base contract with consistent streaming, reasoning display, and permission management.

### The Concept (Analogy)
Like a **universal translator** at the UN. The agent speaks one language (outbound messages). Each adapter translates to a platform-specific format (Telegram markdown, Discord embeds, Slack blocks). The message bus handles routing, permissions, and retry.

### Why vinu-components Needs This
This is a **future feature** — vinu-components is a CLI/API system today. But if it ever becomes multi-user (dashboard, web UI), the channel runtime is the right architecture. Worth noting for long-term vision.

### Priority: LOW — Not needed for Part 2

---

## FEATURE 13: Session Search — FTS5 Full-Text Search

### What It Is
SQLite FTS5 virtual table that enables sub-millisecond full-text search across all conversation history, supporting both English and CJK text with highlighted excerpts.

### The Concept (Analogy)
Like a **library catalog** for conversations. Every message is indexed. You search "momentum decay" and instantly get: which session discussed it, when, and a highlighted snippet showing the context.

### Why vinu-components Needs This
If vinu-research runs 100 research sessions, finding which one tested a specific hypothesis requires manual file browsing. FTS5 search enables instant lookup.

### Priority: MEDIUM — Useful but not blocking Part 2

---

## FEATURE 14: Skill System — Progressive Disclosure

### What It Is
87 specialized knowledge domains, each in its own directory with a `SKILL.md` file. The system prompt gets only one-line summaries; full docs load on demand via `load_skill(name)`.

### The Concept (Analogy)
Like a **doctor's medical reference shelf**. The doctor doesn't memorize every textbook — they know the titles (one-line summaries) and pull the relevant book off the shelf when needed (load on demand). This keeps the doctor's working memory (system prompt) lean while making all knowledge available.

### Why vinu-components Needs This
vinu-research has 15 strategy templates in `generator.py`. As the system grows, a skill system would organize: strategy templates, indicator documentation, backtest guides, and research methodology into discrete, loadable knowledge units.

### Priority: MEDIUM — Organizational improvement, not functional

---

## FEATURE 15: Hypothesis Registry — Research Ledger

### What It Is
A JSON-backed ledger tracking research hypotheses through lifecycle: `exploring → testing → validated → rejected → monitoring`. Each hypothesis links to backtest run cards, creating an auditable chain from idea to evidence.

### The Concept (Analogy)
Like a **scientific journal** for your research. Every hypothesis is a paper: you write the thesis, run the experiment (backtest), record the results (run_card), and the journal tracks whether it was validated or rejected. Over time, you build a body of evidence about what works.

### Why vinu-components Needs This
This is **Feature 2's persistence layer** — it enables the Research Autopilot (Feature 2) to track hypotheses across sessions. Without it, research is ephemeral.

### Priority: HIGH — Required for Feature 2 (Research Autopilot)

---

# Implementation Priority for Part 2

| Priority | Feature | Why |
|----------|---------|-----|
| **P0 — Part 2 Core** | SDM (Feature 1), Hypothesis Registry (Feature 15), Research Autopilot (Feature 2) | These close the loop from Part 2's plan: strategy lifecycle tracking + hypothesis → evidence chain |
| **P1 — Metrics Upgrade** | Multi-Layer Attribution (Feature 4), Validation System (Feature 5), Run Cards (Feature 10) | Strengthen the PASS/REFINE/STOP verdict; make every backtest auditable |
| **P2 — Data Resilience** | Data Loader Fallback Chains (Feature 7), Provider Capability Layer (Feature 8) | Prevent single-source failures; enable multi-provider LLM |
| **P3 — Alpha Infrastructure** | Alpha Zoo (Feature 3) | Enhance vinu-features with lifecycle-tracked factors; 19 operators are high-value |
| **P4 — Advanced** | Shadow Account (Feature 6), Scheduled Research (Feature 9), Security Hardening (Feature 11) | Premium features; build after core is solid |
| **P5 — Future** | IM Channels (Feature 12), Session Search (Feature 13), Skill System (Feature 14) | Not needed for Part 2; organizational/future features |

---

# Cross-Cutting Architecture Patterns

Several patterns recur across Vibe-Trading's features:

1. **Protocol + Implementation separation**: `StrategyStoreProtocol` (abstract) + `InMemoryStrategyStore` / `SqliteStrategyStore` (concrete). `BaseChannel` (abstract) + 16 adapter implementations.

2. **Singleton pattern with thread safety**: `_shared.get_store()`, `get_shared_index()`, `get_default_registry()` all use double-checked locking with `threading.Lock`.

3. **Atomic file writes**: Hypotheses, scheduled research, and run cards all use temp-file → fsync → os.replace patterns to prevent corruption on crash.

4. **Lazy loading / deferred imports**: Channel adapters are imported only when enabled. Alpha modules are imported only on compute. Loader modules are imported lazily by `_ensure_registered()`.

5. **Static analysis over execution**: AST parsing for alpha metadata and generated code validation avoids importing untrusted code. FTS5 for search rather than in-memory string matching.

6. **Graceful degradation**: Price features fall back to NaN. Channels fall back to unavailable status. Loaders fall back through chains. Reports degrade from PDF to HTML-only.
