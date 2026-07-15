# Vibe-Trading → vinu-components Upgrade Map

## Purpose

`vinu-components` (this repo, `/vinu-components/`) and `Vibe-Trading` (HKUDS, MIT-licensed, cloned read-only at `/personal-important/other-reference-repos/Vibe-Trading/`) pursue the same core idea — LLM-driven strategy research over price + ML + news/session signals — but Vibe-Trading is a mature, widely-contributed open-source product and `vinu-components` is an early-stage 8-service pipeline still closing out correctness bugs (see `advanced-part-2-plan.md`).

This doc is a **precise, file-cited map**: for each `vinu-*` service, what exists today, what the equivalent Vibe-Trading subsystem does, exactly what to port, and how it ties into the bugs/phases already scoped in `advanced-part-2-plan.md`. It is meant to be self-contained — an agent reading only this file (plus the cited source files) should be able to start implementing without re-deriving the research below.

**License note**: Vibe-Trading is MIT-licensed (see its `LICENSE`/`NOTICE`). Porting/adapting logic is fine; keep a short attribution comment (`# adapted from HKUDS/Vibe-Trading, MIT license`) on any non-trivial ported function.

**What NOT to trust from Vibe-Trading's own docs**: its README changelog (PR #280) claims a "layered attribution" feature with beta regression + market-regime analysis. Direct code inspection found only the Monte Carlo permutation test half is real, production-wired code (`agent/backtest/validation.py`). Beta-regression / market-regime-classification exist **only as an LLM prompt template** (`agent/src/skills/performance-attribution/SKILL.md`), not executable Python. Don't plan around code that isn't there — verify against the file paths cited below before relying on anything.

---

## Quick orientation

| | vinu-components | Vibe-Trading |
|---|---|---|
| Root | `/home/somic_cps/Vina/my-trading-work-3/vinu-components/` | `/home/somic_cps/Vina/my-trading-work-3/personal-important/other-reference-repos/Vibe-Trading/` |
| Shape | 8 sibling FastAPI microservices + shared `vinu-lib` | Single Python backend (`agent/`) + React frontend, PyPI package |
| Services relevant here | `vinu-stock-price`, `vinu-news`, `vinu-correlation`, `vinu-features`, `vinu-simulator`, `vinu-research`, `vinu-strategy`, `vinu-lib` | `agent/backtest/loaders/`, `agent/src/tools/`, `agent/src/factors/`, `agent/backtest/validation.py`, `agent/src/swarm/` |

---

## 1. `vinu-stock-price` ← Vibe-Trading `agent/backtest/loaders/`

### Current state (vinu-stock-price)
3 providers: `vinu_stock/providers/{alpaca,polygon,yahoo}.py`, dispatched through `ProviderRegistry.fetch_bars_with_fallback()` (`providers/registry.py:48`) using role-based chaining (backfill/live/fallback) read from `providers.yaml`. Storage is Parquet (`storage/parquet.py`) partitioned `data/prices/1m/{SYMBOL}/{archive,live}/{YYYY}.parquet`, catalog in `meta.db`.

### What to port

| Vibe-Trading source | What it does | Port target | Why |
|---|---|---|---|
| `agent/backtest/loaders/base.py:50` `validate_ohlc()` | Structural OHLC guard: `high<low`, non-positive prices, bad bracketing, with `strategy="drop"/"warn"/"raise"` | New `vinu_stock/validation.py`, called at the point bars are written to Parquet in `storage/parquet.py` | You've had silent-zero-row failures twice already (bugs #1, #3 in the Part 2 plan). A structural boundary guard on every write catches malformed bars *before* they poison downstream features, independent of which provider produced them. |
| `agent/backtest/loaders/base.py:144-217` `retry_with_budget`/`check_budget` | Wall-clock deadline + fixed backoff schedule `(0.5,1.5,4.0)s`, applied only to a declared "transient" exception class, terminal failure wrapped in `TimeoutError` with `__cause__` preserved | Replace whatever ad hoc retry exists in `providers/{alpaca,polygon}.py` | Cleaner failure semantics than silent swallowing — directly relevant since bug #1 was a *silently swallowed* exception. A budget-based retry that re-raises with cause is the opposite failure mode. |
| `agent/backtest/loaders/_http.py:46-103` `HostThrottle` | Process-wide, per-host minimum-spacing gate + jitter, shared `requests.Session` per host | New `vinu-lib/http_throttle.py` (shared, see §8), used by both `vinu-stock-price` and `vinu-news` | Neither service currently rate-limits itself against the external API host; this is exactly the class of problem that produced Vibe-Trading's Eastmoney-CDN-block issues. Cheap insurance before you hit the same wall. |
| `agent/backtest/loaders/base.py:220-576` content-addressed cache + `loader_cache_range_is_final()` staleness guard | SHA-256(`version,source,symbol,timeframe,start,end,fields`)-keyed Parquet cache; **refuses to cache any range whose `end_date` is today-or-future**, so an in-progress bar is never pinned | Not urgent — your Parquet-per-year storage already is the cache. But the **staleness-guard idea** (never persist/trust a bar for a still-forming period) is worth an explicit check in `backfill/orchestrator.py` if it doesn't already exist. | Prevents a subtly wrong "final" value for today's incomplete bar from being trusted as settled. |
| `agent/backtest/loaders/registry.py:118` `_NO_NETWORK_FALLBACK_SOURCES` pattern | If a caller explicitly names a source (e.g. `local`) and it's unavailable, the registry refuses to silently substitute a different source — raises instead | `ProviderRegistry.fetch_bars_with_fallback()` (`providers/registry.py:48`) — audit whether an explicit `provider=` request can currently silently fall back to a different provider | Silent substitution is the same failure class as bug #1's "0 rows, no error" — an explicit request that gets quietly rerouted to a different data source could produce numbers a user thinks came from Alpaca but didn't. |

**Not worth porting**: the other 17 loaders (tushare, akshare, okx, etc.) — they're for A-share/crypto/India markets you're not targeting; Polygon+Alpaca+Yahoo already covers US equities with a fallback chain, which is the architecturally important part you already have.

---

## 2. `vinu-news` ← Vibe-Trading `agent/backtest/loaders/rsshub_events.py` + `agent/src/tools/*`

### Current state (vinu-news) — this is more built-out than the Part 2 plan assumed
Real RSS ingestion (22 feeds, `rss/config/feeds.yaml`) + 3 ticker-news providers (Yahoo/FMP/Alpaca, `providers/registry.py:17`) + a **fully rule-based enrichment pipeline** (`analysis/enrichment/enrich.py:33`) producing structured fields per article: `sentiment`/`sentiment_score` (lexicon-based, `sentiment.py:248`), `category`, `impact`, `priority`, `threat`, plus dedup/NER/threading. A separate opt-in LLM pass (`analysis/llm/analyze.py:23`) adds `{sentiment_score, confidence, risk_flags, summary}` per article on demand. **This already produces structured, non-narrative data** — the Part 2 plan's bug #8 framing ("news only exists as narrative") undersold what vinu-news itself can produce; the actual gap is that nothing merges it into a **per-bar numeric column** the way `sma_20`/`rsi_14` are merged.

### What to port — this is the highest-leverage single item in this whole doc

| Vibe-Trading source | What it does | Port target | Why |
|---|---|---|---|
| `agent/backtest/loaders/rsshub_events.py:501` `enrich_price_frames_with_events()` | Attaches **two numeric columns per price bar**: `event_score` (exponentially age-decayed sum of in-window article scores, `decay_lambda` per day, clipped `[-1,1]`) and `event_count` (raw count of contributing articles in the lookback window) | New function in `vinu-news` (e.g. `vinu_news/analysis/per_bar_features.py`), or in `vinu-correlation` if you want it colocated with the price-alignment logic already there (`vinu-correlation` already computes hourly-resampled news volume/sentiment vs. price in `engine/correlation.py`) | **This is exactly Phase 3 of `advanced-part-2-plan.md`** ("news-fusion: turn news into a per-bar feature, not just narrative"). vinu-news already has richer per-article scores than Vibe-Trading's lexicon (`sentiment_score`, `impact`, `category`, `priority`) — you don't need Vibe-Trading's scorer, just its **decay-weighted aggregation-into-a-column** pattern, fed by your own richer per-article fields instead of their lexicon. |
| `agent/backtest/loaders/rsshub_events.py:264` `_knowable_date()` | A publication at/after a cutoff hour (default 16:00) rolls to the next calendar day before being considered "knowable" — a point-in-time-safety guard against lookahead bias | Apply the same rule wherever `event_score`/`event_count` get computed per bar (§ above) | Without this, an after-hours headline could leak into the same day's bar during backtesting — a subtle lookahead bug that would look exactly like a legitimate signal in a backtest and be undetectable without this check. Cheap to add, easy to skip and regret. |
| `agent/backtest/loaders/rsshub_events.py:239` pluggable `scorer` callback design | The scoring function is swappable (lexicon by default, LLM judge pluggable) | Design the new `per_bar_features` function so the article→score mapping is a parameter, not hardcoded — pass `sentiment_score`/`impact` straight from vinu-news's existing `enrich_article()` output | Keeps the aggregation logic decoupled from whichever per-article scoring method is live, so future LLM-analysis improvements (or A/B testing lexicon vs. LLM scoring) don't require touching the per-bar merge code. |

**Not worth porting**: Vibe-Trading's `get_stock_news` agent tool — it returns pure narrative/matches with no score, i.e. it's *behind* what vinu-news already does. Also skip its lexicon sentiment scorer (`sentiment.py` in Vibe-Trading) — vinu-news's own lexicon (`analysis/enrichment/sentiment.py:248`, ~90-entry financial phrase table) is comparable or better and already integrated with category/impact/priority.

**Cross-check against Part 2 plan**: this closes bug #8's real gap (session/news not real per-bar inputs) for the news half specifically. Phase 2 (session-as-feature) is unrelated to this and still needs its own small pure-function build (`vinu-features/compute/indicators/session/`) as already scoped.

---

## 3. `vinu-features` ← Vibe-Trading `agent/src/factors/{base,registry,bench_runner,bench_runner_strict}.py`

### Current state (vinu-features)
23 named indicators + `bigger_recipe` packs: `alpha158`/`alpha360` are genuine Qlib-style ports; **`alpha101` is mostly synthetic filler — only 10/101 formulas are real (`alpha101.py:5-16`), the other 91 are template-generated** (`alpha101.py:19-40`). 9 ML models exist (`compute/ml_models/`) but **all fit-and-predict on the same array, no train/test split** (bug #7, root-caused, not fixed).

### What to port

| Vibe-Trading source | What it does | Port target | Why |
|---|---|---|---|
| `agent/src/factors/bench_runner_strict.py:299` `run_bench_strict()` | Same-universe **random control**: cross-sectionally shuffles the factor *within each row* (date) `n_seeds` times (`_shuffle_within_rows`, line 99), computes `alpha = signal_IC − random_IC` paired per date, t-tests that paired series against zero. Rejects a factor whose IC is just tracking cross-sectional beta — a stricter bar than "OOS correlation > 0." Also supports an explicit `oos_split` date boundary. | `vinu-features/compute/ml_models/registry.py` — this **is** Phase 1.1–1.3 of the Part 2 plan, done properly | This directly targets the exact bug reproduced this session: `random_forest` gave **0.878 correlation** — a naive 80/20 holdout split (as currently scoped in Phase 1.1) might still pass if the model is tracking a shared market-beta artifact rather than real signal. The random-control test is specifically designed to catch that failure mode (the module's own docstring cites a real incident: only 1/12 factors survived this test after passing a naive IC-vs-zero test). **Recommend upgrading Phase 1.1–1.3 to use this pattern instead of a plain holdout split.** |
| `agent/src/factors/registry.py:376` `_validate_output()` "sanity gates" | Four checks before trusting any factor's output: (1) is a DataFrame, (2) shape matches the price panel exactly, (3) no `+/-inf` anywhere, (4) NaN ratio ≤ 95% | New helper in `vinu-features/compute/registry.py`, applied to every indicator/ML-model output, not just the alpha packs | Cheap, generic correctness net — would have caught bug #3 (silently-dropped rows producing `row_count: 0`) at the point of feature computation rather than requiring a live investigation. |
| `agent/src/factors/registry.py:147` `load_alpha_meta_from_py()` — AST-only metadata scan, no import at scan time | Discovery of ~450 factor files by parsing a `__alpha_meta__` dict literal via `ast.literal_eval`, without ever importing (and thus never crash-risking on) the file's `compute()` body | Not urgent at your current scale (23 indicators + a few packs), but worth adopting **if/when** you port real Alpha101 formulas (below) — a broken formula file shouldn't block discovery of the other 100 | Low priority; note for later. |
| `agent/src/factors/base.py:61-353` — 17 operators (`rank`, `ts_rank`, `decay_linear` via `einsum` ~40× faster, `ts_argmax`/`ts_argmin` via `bottleneck` ~350× faster, `safe_div` that never produces `inf`) | Reusable vectorized building blocks every alpha formula composes from | Compare against whatever `bigger_recipe/_alpha_expr/evaluator.py` already provides — if your alpha158/360 ports reimplement rolling-window ops less efficiently, these are drop-in speedups, and `safe_div`'s zero-denominator-never-`inf` behavior is a correctness detail worth matching. | Medium priority — a performance/robustness upgrade, not a bug fix. |

**Alpha101 completeness — needs verification, don't assume**: Vibe-Trading's own factor zoo lives at `agent/src/factors/zoo/alpha101/` in their repo. The research pass for this doc did **not** verify how many of the 101 formulas are real there either — check before porting. If real, porting the missing 91 formulas from their zoo files (MIT-licensed) is strictly better than the current template-generated filler in `vinu-features/compute/bigger_recipe/alpha101/alpha101.py:19-40`; if not, this is a shared gap and not a quick win.

---

## 4. `vinu-correlation` ← Vibe-Trading `agent/backtest/validation.py`

### Current state (vinu-correlation)
Real Granger causality (`engine/granger.py:10`, degrades silently to a fixed non-causal result if `statsmodels` missing — `api.py:126-132`), event-study impact windows, drawdown attribution with a **hardcoded placeholder** for market-beta contribution (`market_pct = 0.0 if market_returns is None else 0.2`, `engine/drawdown.py:113` — and `market_returns` is never actually passed by any caller, so this is always `0.0` in practice today).

### What to port

| Vibe-Trading source | What it does | Port target | Why |
|---|---|---|---|
| `agent/backtest/validation.py:28` `monte_carlo_test()` | Shuffles trade PnL order `n_simulations` times (default 1000), recomputes Sharpe/max-DD per shuffle, reports `p_value_sharpe`/`p_value_max_dd` = fraction of shuffles beating the real path | New module, e.g. `vinu-simulator/vinu_simulator/engine/significance.py`, called from `routes_read.py` alongside existing metrics, or from `vinu-research`'s post-backtest step | Directly answers "is this Sharpe real or luck" — relevant to Phase 5 (configurable risk targets) and to the plan's own suggestion #1 (regression suite): a strategy that clears `sharpe >= 1.5` by chance on a thin 6-month window (explicitly flagged as a risk in plan suggestion #6) would show up as a high Monte Carlo p-value. |
| `agent/backtest/validation.py:99` `bootstrap_sharpe_ci()` | Resamples daily returns with replacement to build a Sharpe confidence interval | Same module as above | `vinu-correlation` already uses `scipy.stats.bootstrap` for correlation CIs (`engine/correlation.py`) — same technique, just needs applying to the simulator's Sharpe series too. Cheap given the pattern already exists in your codebase. |

**Vibe-Trading's own gap, not a port target**: their drawdown/attribution code has no real beta-regression either (confirmed above — the changelog's claim doesn't match the code). Your `market_pct = 0.2` placeholder in `engine/drawdown.py:113` is a genuine gap on both sides; you'll need to build the actual regression yourselves rather than porting one.

---

## 5. `vinu-simulator` — mostly internal fixes, one adjacent port

No major Vibe-Trading subsystem maps directly onto `vinu-simulator`'s core weight/cost engine. Two things worth noting:

1. **Not a port, but blocks everything above**: `CustomSimulateRequest` (`server/schemas.py:67-80`) has no `indicators` field, so `vinu-research`'s requested indicators (`tools.py:109-110`) are silently dropped by pydantic, and `requested_indicators` stays hardcoded to `["sma_20","sma_50","rsi_14"]` (`service.py:150`). **This must be fixed before Phase 2/3 (session, news-as-feature) can work at all** — the merge point (`engine/custom_sim.py:47-51`) is already correct and ready to receive new columns; the request schema is what's silently eating them.
2. Consider hosting the Monte Carlo/bootstrap significance module (§4 above) here instead of `vinu-correlation`, since Vibe-Trading places the equivalent (`validation.py`) directly in the backtest engine (`engines/base.py:471-482`, step 7 of `run_backtest`) rather than in a separate correlation/attribution service. Either placement works; just pick one and keep `vinu-research` calling a single significance endpoint.

---

## 6. `vinu-research` ← Vibe-Trading `agent/src/swarm/*`

### Current state (vinu-research)
Single-threaded iteration: one Quant Coder function (`_default_quant_coder`, `loop.py:564`) → one backtest → one Risk Critic function (`_default_risk_critic`, `loop.py:902`, rule-based + optional LLM) → PASS/REFINE/STOP. Bug #13 (Part 2 plan): **the critic's suggestions are never verified against the next iteration's actual code** — a `.diff()` state bug that broke position-holding was invisible to the critic, which kept suggesting generic filters instead.

### What to port

| Vibe-Trading source | What it does | Port target | Why |
|---|---|---|---|
| `agent/src/swarm/task_store.py:150` `validate_dag()` + `:203` `topological_layers()` (Kahn's algorithm) | Cycle-checks a task DAG, then computes parallel-executable layers from `depends_on` edges | Restructure `vinu-research/vinu_research/loop.py` around an explicit small DAG: `generate → backtest → static_verify → critic_review`, where `static_verify` is a **hard dependency gate** before `critic_review` ever runs | This is the structural fix for bug #13. Today the critic reviews backtest *output* only; it never confirms the code does what it claims. Making static verification a blocking upstream task (not just a suggestion) means a `.diff()`-style state bug gets caught mechanically before the critic wastes a cycle theorizing about it. This is also literally what Phase 5.4 already asks for ("cheap static verification pass... before it's trusted") — the DAG pattern is just a cleaner way to wire it than an inline function call. |
| `agent/src/swarm/models.py:88` `SwarmTask.input_from` + `worker.py:182` `build_worker_prompt()` splicing upstream results into a `{upstream_context}` placeholder | Explicit, typed data flow between agent stages instead of ad hoc dict-passing | Adopt this shape for `loop.py`'s critic step: the critic's prompt should receive the *verification task's* structured pass/fail result as a typed field, not just narrative | Ties Phase 4 (structured news attribution feeding the critic, e.g. "15% win rate near earnings news vs 55% baseline") and Phase 5.4 (static verification) into one consistent "upstream tasks feed typed context to downstream agents" pattern instead of two bespoke mechanisms. |
| `agent/src/swarm/presets/investment_committee.yaml` pattern: parallel independent researchers (bull/bear) → a risk-review layer → a single decision-making synthesis agent | A 3-layer DAG, not a 2-step generate/critique loop | Optional, larger restructure: if you want multiple candidate strategies generated in parallel per iteration (vinu-research's `ResearchConfig.llm_candidates` already implies this is wanted — `comparison.py:rank_candidates` exists), this is the reference shape for how to fan results back into one critic rather than critiquing one candidate at a time | Not required for the Part 2 plan's scope, but if multi-candidate generation becomes a priority later, don't reinvent this — it's already a proven pattern in Vibe-Trading with 30 working presets. |

**Not worth porting**: the full `ThreadPoolExecutor`-per-layer runtime (`runtime.py:_execute_run`) — that's infrastructure for running many *independent LLM agents* concurrently (investment-committee style), which is a bigger lift than vinu-research's single-strategy refinement loop currently needs. Take the DAG *shape*, not the executor.

---

## 7. `vinu-strategy` ← Vibe-Trading `agent/src/factors/registry.py` (sanity-gate pattern)

`vinu-strategy`'s `RulesEngine` (`engine/rules_engine.py:11`) and `StrategyRegistry` (`engine/registry.py:14`) are architecturally similar to Vibe-Trading's factor registry (YAML/declarative definitions, dispatched by method name) but have no equivalent to the **sanity gates** (`registry.py:376`) applied before a factor's output is trusted. Since `vinu-strategy` already produces target weights from YAML-declared rules, apply the same 4-check gate (shape match against the input panel, no `inf`, NaN ratio ceiling, plus — specific to weights — a check that the weight series holds nonzero values across multiple consecutive bars, which is literally Phase 5.4's request) before a strategy's weights are handed to the simulator.

---

## 8. `vinu-lib` — where the shared infrastructure should land

`vinu-lib` today is generic plumbing (`server.py`, `client.py`'s `ResilientClient`/`CircuitBreaker`, `sqlite.py`, `db.py`, `parquet.py`, `config.py`, `rate_limit.py`) with **no domain schema layer** — the recently-added `data/shared/` directory is scaffolded but empty (`.gitkeep` only), nothing reads/writes it yet. Candidates to add here, since multiple services would use them:

| New `vinu-lib` module | Ported from | Used by |
|---|---|---|
| `http_throttle.py` — per-host `HostThrottle` w/ jitter | `agent/backtest/loaders/_http.py:46-103` | `vinu-stock-price`, `vinu-news` |
| `ohlc_validate.py` — `validate_ohlc()`/`validate_date_range()` | `agent/backtest/loaders/base.py:31,50` | `vinu-stock-price` (write boundary), possibly `vinu-features` (read boundary) |
| `sanity_gates.py` — shape/inf/NaN-ratio checks | `agent/src/factors/registry.py:376` | `vinu-features` (ML models, alpha packs), `vinu-strategy` (weight output) |
| `significance.py` — Monte Carlo permutation + bootstrap Sharpe CI | `agent/backtest/validation.py:28,99` | `vinu-simulator` or `vinu-correlation` (pick one, see §5) |

`vinu-lib`'s existing `rate_limit.py` (`TokenBucket`) already covers part of what `HostThrottle` does — check for overlap before adding a second rate-limiting primitive; you may only need to add the per-host keying + jitter on top of what's there.

---

## Suggested integration order (maps onto `advanced-part-2-plan.md`'s phases)

1. **Fix `vinu-simulator`'s `CustomSimulateRequest.indicators` gap first** (§5) — nothing from Phase 2/3 works until requested indicators actually reach the simulator. Not a port, just a bug fix, but it's the literal blocker.
2. **Phase 1 (ML measurement)** — use `bench_runner_strict`'s random-control pattern (§3) instead of a plain holdout split. Stronger, and the plan's own reproduction (0.878 correlation) is exactly the failure mode it's built to catch.
3. **Phase 2 (session)** — unchanged, no Vibe-Trading equivalent needed; build as already scoped.
4. **Phase 3 (news-as-feature)** — port `enrich_price_frames_with_events()`'s decay-weighted aggregation (§2) feeding off vinu-news's own richer per-article fields. This is the single highest-value port in this doc.
5. **Phase 5.4 (static verification)** — adopt the sanity-gate pattern (§3, §7) plus the DAG-as-hard-gate restructure (§6) for the critic loop.
6. **Phase 4 (attribution) / plan suggestion #1 (regression suite)** — add the Monte Carlo/bootstrap significance check (§4/§5) as a cheap addition to whatever regression suite you build.

Everything else in this doc (extra data-loader hardening in §1, the operator-library speedups in §3, the multi-candidate swarm shape in §6) is valuable but not on the critical path the Part 2 plan already committed to — treat as backlog, not blockers.
