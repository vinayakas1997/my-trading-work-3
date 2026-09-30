# HOW the system is implemented (per-feature, verified against code 2026-09-30)

Companion to `vision-trding-system.md` (WHAT+WHY). This file is HOW + WHERE + one running
scenario per feature. Every path below was traced to real files in `vinu-components/` on
2026-09-30 — no stale docs mixed in.

Stale rule applied: `project-understanding/`, `personal-important/`, older
`missing-pieces-of-system/` subfolders were inventoried for awareness only. Anything that
contradicts current code (old angle counts like "28/29", "maturity prompt-only", "no exit
mechanism", "seed-only tickers", "no graveyard", "no precondition write-back") is marked
STALE and the code truth is stated instead. Current truths: 30 angle packages with compute.py
(35 dir entries), maturity consults risk+live-decision+capital, exit/review exists, live screener
intersection exists, graveyard + generation store + precondition store exist.

Running example used throughout: **AAPL, 15m strategy `sma_cross_live`** (must-condition
`sma5_cross_sma50`, confirmation `adx_14 > 20`, `live_decision_position_size=0.02`).

All service ports (defaults): stock 8081, tools/features 8082, initial-analysis 8083,
strategy 8084 (via quant-core-api), simulator 8085, research 8087, portfolio 8090, live 8091,
reflection 8092, agent 8080-ish (`services{}` map in `vinu-agent/vinu_agent/config.py`),
screener 8095. Route prefixes: `/stock`, `/news`, `/research`, `/simulator`, `/strategy`,
`/agent`, `/live`, `/reflection`, `/screener`.

---

## 1. Discovery — vinu-screener ranking + filters

WHERE: `vinu-screener/vinu_screener/rankers/runner.py:50 RankerRunner.run()` →
`pipeline/pipeline.py:52 PipelineResult` (`ranked,trace,top,enrichment,turnover_held,
rejected_samples`); `pipeline/hard_filter.py:25 HardFilterConfig` (`min_history_bars`,
`min_price=5.0,min_dollar_volume=1M` per `rankers/seed.py`); `pipeline/rule_filters.py:193
FilterChain` (`MAX_REJECTED_SAMPLE_PER_STAGE=20`); server `server/app.py:269 POST
/screener/rankers/{id}/rank`, `:293 GET .../latest`, `:303 GET .../churn`.
Shared shape: `vinu_infra/rejection_log.py RejectionRecord/record_rejection()`.
HOW: fetch universe once → `min_history_bars` gate before scoring (thin/recent listings never
reach top-N; matches Track-1 `MIN_OBSERVATIONS=70`) → hard-filter → risk-veto → score → top-N +
rotation (`PipelineConfig top_n=20,rotation_band=1.5`) → snapshot persisted (trace included since
fix; was stranded). Drops recorded per stage with bounded samples + `veto_reason` on the
candidate (was computed-then-dropped before fix).
KNOBS: `hard_filter{min_history_bars,min_price,min_dollar_volume}`, `top_n`, `screener_ranker_id`.
SCENARIO: nightly `POST .../rank` scores 2000 symbols; AAPL passes history gate (800 bars),
ranks #7; XYZ-IPO (30 bars) rejected with `rejection_category=insufficient_history`, visible in
`rejected_samples`, never reaches research.

## 2. Live ticker source — planner-worker intersection

WHERE: `vinu-agent/vinu_agent/cli.py:434 planner_worker_main` (`VINU_AGENT_SCREENER_RANKER_ID`,
`VINU_AGENT_WATCHLIST_SEED_TICKERS`, `TickerSummaryStore.list_summaries()`,
`fetch_screener_top_tickers()`); triage `agent/planner_triage_hook.py PlannerTriage`,
`agent/thesis_intake_gate.py K_CAP_DEFAULT=3, K_CAP_WINDOW_DAYS=7`.
HOW: if ranker configured → per-cycle source = screener current top ∩ bootstrapped summaries
(mid-bootstrap excluded, not half-processed); seed list additive override (human never dropped);
unset/fetch-fail → old full accumulation (fail-open, strict improvement, opt-in gated).
Consequence (named, not hidden): unranked+unseeded ticker stops refresh — that IS live discovery.
SCENARIO: screener top = {AAPL,NVDA}; store has {AAPL,NVDA,OLD}; seed={AAPL}; cycle processes
{AAPL,NVDA}; OLD skipped until re-ranked.

## 3. Market data — stock candles + news (point-in-time safe)

WHERE: `vinu-stock-price/vinu_stock/server/routes_read.py:79 candles()` (`GET /stock/candles/{symbol}`,
`POST /candles/batch`, `GET /quote /events /catalog`); `query/engine.py:145 fetch_candles()`;
`query/indicators.py:68 apply_indicators()` delegates to `vinu_tools.compute.indicators.*`
(SMA/RSI/MACD/macd_signal/daily_return/volatility_20d/ADX); `query/cache.py IndicatorCache`;
`providers/yfinance.py:39 _retry` (`_FETCH_RETRIES=3,_RETRY_SLEEP_SEC=1.0`); `catalog/
gap_validation.py count_session_gaps()`; `vinu-news/vinu_news/server/routes_read.py:53 ticker_news()`
(`GET /news/ticker/{symbol}`); `analysis/storage/models.py:50 ArticleRecord
(published_at/ingested_at/publish_time_is_estimated)`; `analysis/enrichment/enrich.py:34
enrich_article()` (9 stages); shared `vinu-infra/point_in_time.py:24 clamp_to_as_of()`.
HOW: every read takes absolute `as_of` (unix-sec replay boundary); server clamps `to` and emits
`X-Clamped-To-As-Of`, `X-Cache-Age-Seconds`, `X-Data-Empty`, `X-Session-Gap-Count` (1m-only).
News `sort_ts = published_at or ingested_at` (old silent conflation fixed) + round-trip tested.
Other relative-window routes still need per-route `as_of` semantics — open design, not wired.
SCENARIO: replay `as_of=<Tue close>` → AAPL candles stop at Tue close even if Wed exists
(`X-Clamped-To-As-Of:true`); news article with missing publish date flagged
`publish_time_is_estimated=true`, never counted as pre-trigger evidence if after trigger.

## 4. Indicator math — single implementation

WHERE: blessed `vinu-tools/vinu_tools/compute/registry.py:346 apply_indicators(rows,names)`,
`:157 get_indicator_module()`, `:330 warmup_bars_for_features()`; doc rule in
`vinu-tools/AGENTS.md`; risk `compute/risk/shock_correlation.py:58 dcc_shock_correlation()`
(+gerber+garch), re-exported by `vinu-portfolio/vinu_portfolio/shock_correlation.py`.
HOW: all callers use `apply_indicators` / `compute(rows,name=)`; ADX/ATR Wilder bugs fixed once in
`vinu-tools`; 4 audit instances closed (Track-1, screener RSI-seed, trend_lifecycle true-range,
stock-price delegation); one deliberate non-fix: `trend_lifecycle/snapshots.py` ~90-line private
library stays (persisted KNN comparability — needs migration decision); root-cause enforcement
(blessed-path lint/docs) = remaining item.
SCENARIO: AAPL RSI(14) from screener ranker, live detector, and backtest all resolve to the same
`vinu_tools` function — no divergent rank-vs-trigger numbers.

## 5. Understanding — 30 analysis angles

WHERE: `vinu-initial-analysis/vinu_initial_analysis/angles/` (30 `*/compute.py`);
`signal_evidence/compute.py:101` (`MUST_CONDITION_NAME=sma5_cross_sma50`, `MIN_OBSERVATIONS=70`,
`FORWARD_HORIZON_BARS=20`, `NEWS_CONFOUND_WINDOW_MINUTES=60`); `regime_analysis/compute.py
classify_regime()/compute_regime_frame()` (PIT-safe z-scores, `MIN_OBSERVATIONS=141`);
`trend_lifecycle/{compute,lifecycle,peaks,signals,snapshots,patterns}.py` (`patterns.py:93
find_similar(k=5, before_ts walk-forward, session pool≥10)`, high-conf `>0.85`);
`search_trends/compute.py` (pytrends `today 12-m`, 12-wk baseline, `no_data` fail-open +
`backtest.py` forward-return correlation); `storage/{orchestration,orchestration_registry,run_id}.py`;
`catalog/angles.yaml`.
HOW: per ticker+bars(+news) → per-angle rows keyed by `analysis_until` + `days_stale` fresh at read
(option-a backfill visibility; auto-fill orchestrator = open). Regime + news-confound
(`news_confound{occurred,minutes_before,article_id}`, ≤ trigger only) stored in flexible
`indicators` dict (real payload has no `session/day_of_week` fields — checked, not assumed).
SCENARIO: AAPL backfill records SMA-cross trigger + regime `bull` + `news_confound{occurred:false}`;
KNN finds 5 similar past peaks (all `bar_ts < before_ts`) → analogous avg +1.3%.

## 6. Research generation — drafts that remember history

WHERE: `vinu-research/vinu_research/llm_generator.py LlmStrategyGenerator(generate:351,refine:417)`;
`loop.py StrategyResearchLoop(run:207, generation_candidate_store=None→injected)`;
`models.py Evidence(metric_kind=sharpe default)`, `Hypothesis`, `TradeScoreResult`;
`hypothesis_registry.py add_evidence()` (Sharpe-only promotion `best_sharpe` 0.3/0.5; else
append-only); `signal_evidence_bridge.py sync_signal_evidence_to_hypotheses()` (exact
`signal_definition==must_condition`, one summary/call, never auto-create);
`storage/signal_evidence_store.py`; `idea_similarity.py` (TF-IDF screen) + `llm.py
check_duplicate_idea()` (one call, "not duplicate" trusted; threshold fallback only when
LLM absent/fails); `generator.py list_recipes()`.
HOW: 3 drafts/call → heuristic complexity-penalty rank → winner researched, all recorded
(`generation_candidate_store.py`, `code_hash` identity, `GET /research/generation-rounds[/{id}]`;
store defaults None, `ResearchService` injects — avoids test-file writes). Prompt already pulled
`evidence[-3:]`; fix renders full `reasoning` for `signal_evidence` kind only. Dedup correction
recorded: `indicators_used` can't apply at idea-time (doesn't exist yet) → two-tier free-text fix.
SCENARIO: idea "SMA crossover AAPL" → TF-IDF screens 2 candidates → LLM says #2 duplicate →
matched to `hyp_..._sma_cross` (no new hypothesis); prompt includes "12 triggers, 58% positive,
last fired 3d ago" (full reasoning, not bare metric).

## 7. Validation — sweep grid that keeps losers + graveyard

WHERE: `sweep_store.py SweepGridStore` (`sweep_runs`+`sweep_grid_points`, `persist=False` on
walk-forward inner grids); `sweep_grid.py run_sweep_grid()` (`SweepGridResult
sweep_id,ranked,walk_forward,pbo`); `server/routes_sweep.py` (`POST /research/sweep/grid` returns
`sweep_id`; `GET .../{sweep_id}`, `GET ...?symbol=`; `POST /sweep/candidate`, `GET /sweep/recipes`);
`sweep_grid.py param_diff_from_winner` → `_serialize_grid` → HTTP; `candidate_graveyard.py
query_candidate_graveyard()` (read-time union, `source=generation|sweep|hypothesis`,
ISO-normalized sort) + `GET /research/candidate-graveyard/{symbol}`; `service.py ResearchService`.
HOW: every grid point persisted, winner AND losers with real failure reason; graveyard is query not
4th table (no store changes; code_hash→sweep join + blocking-gate = deliberately open).
SCENARIO: AAPL grid 12 points → winner `(5,50)` Sharpe 1.1; 11 losers kept (e.g. `(5,200)`
`worse_sharpe vs sweep_<id>`); graveyard for AAPL lists generation-discard + sweep-failures +
hypothesis rejection newest-first.

## 8. Backtest engine — simulator with 4 sizers + guards

WHERE: `vinu-simulator/vinu_simulator/engine/simulator.py WeightSimulator.simulate()` (cost model, sizer
build, config-hash cache; `dry_run` → stub); `engine/custom_sim.py simulate_custom()`;
`engine/sizing.py build_position_sizer(fixed|vol_target|kelly|composite|evidence_confidence|
regime_aware|drawdown_aware)` — `CompositeSizer` (vol×DCC shrink), `EvidenceConfidenceSizer
(min_confidence_scale=0.5,min_sample=5)` (per-symbol, `evidence_triggers` pre-fetched — no caller
wires it yet), `RegimeAwareSizer({high_vol:0.5,bear:0.7,bull/sideways:1.0})` (benchmark-level),
`DrawdownAwareSizer(ok1.0/halve0.5/flat0/halt0, halt non-sticky)`; `engine/metrics.py`
(Sharpe/Sortino/MDD/VaR/CVaR); `engine/ast_guard.py validate_code()` (Call+Attribute sandbox fix);
`storage/meta.py simulation_run_symbols(run_id,symbol)` indexed join; `clients/{price_client
(LRU×2),features_client(LRU),strategy_client,base}.py`; `service.py SimulatorService`;
`models/simulation.py (SimulationConfig/Input/Result)`; `server/routes_read.py` (`POST
/simulator/simulate`, `POST /simulate/custom` with schema-version echo, `GET /results/...`,
`GET /runs?strategy&symbol`, `DELETE`, `GET /health`); `server/schemas.py`
(`CUSTOM_*_VERSION=contract_version(...)`).
HOW: research HTTP → simulator fetches weights+prices (cached, one long-lived client each) →
sizer scales → metrics → rows persisted + indexed by symbol. AST guard blocks attribute-escapes
(`os`/`subprocess` via `.`), not just calls.
SCENARIO: AAPL custom code `class MyStrat` → `POST /simulate/custom` → regime-aware 0.7× in bear
→ Sharpe 1.4, MDD −8% → `run_id` queryable by symbol.

## 9. TradeScore + EV + R:R floor + decay (self-calibrating checklist)

WHERE: `vinu-research/vinu_research/trade_score_calibration.py` (thresholds, `trade_score_calibration.json`
atomic tmp+replace, `...history.jsonl`); `gates/trade_score_gate.py compute_trade_score()`,
`check_trade_score_gate()`, `_reward_risk_ratio()` (veto `<min_reward_risk_ratio` → `no_trade`),
`TIER_SIZE_MULTIPLIER{strong1.0,moderate0.7,watch0.4,no_trade0}`; `config.py
TradeScoreThresholds(strong110/moderate90/watch70, confluence40/ev35/risk30/regime30,
ev_full2%,risk_full10%,cost10bps,min_tier watch,min_R:R1.5)`; `decay.py` (metrics/health/snapshot/
BENCHING→ACTIVE→MONITORING→DECAYED→DISABLED transitions).
HOW: score = confluence+EV+regime-fit+risk (calibrated weights nudge toward historically winning
sub-scores, bounded `trade_score_calibration_bound=0.2`, `min_sample=30`); hard R:R floor enforced
in `trade_plan_authoring` gate chain (earlier "partial" claim corrected — already enforced).
SCENARIO: AAPL confluence 32/40 + EV 28/35 + regime 24/30 + risk 25/30 = 109 → `moderate` ×0.7;
R:R 1.2 → forced `no_trade` regardless of 109.

## 10. Trade-plan authoring + forecast prompt (maturity-aware)

WHERE: `trade_plan_authoring.py author_trade_plan()` (maturity block `:893-908`, risk-band
half-Kelly 10% cap, `approve_trade_plan()`, `record_realized_outcome()`); `forecast_skill.py
generate_forecast()` + `_build_forecast_prompt()` (`=== System Maturity ===` alongside
`=== Angle Digest ===`, fails open like options/debate blocks); `maturity_assessor.py assess()`
(raw sqlite on `paper_performance.db` — avoids vinu-agent circular dep; research-api path can't see
paper history → never `paper_only` there, documented asymmetry); `config.py
maturity_tier_enabled=False`, `agent_data_root`, `trade_score_calibration_min_sample=30`;
`server/routes_introspect.py:209 GET /research/maturity/status` (always-on).
HOW: opt-in flag → `assess()` → `{tier,n_real_trades,paper_days,accuracy,regime_coverage}` →
prompt block + weight guidance (backtest-heavy at cold_start/paper_only, live-heavy at mature).
SCENARIO: cold_start (0 live, 2 paper days) → prompt carries tier+evidence + "weight backtest,
cap size, hedge language"; mature flips guidance to live-calibration.

## 11. Strategy execution — daily weights (point-in-time safe)

WHERE: `vinu-strategy/vinu_strategy/models/strategy.py StrategyConfig` (`schedule,features/correlation/
angles_required,pipeline{selection/allocation/timing/risk},universe,metadata,must_conditions[],
confirmation_conditions[],grace_window_bars=10,precondition{description,defined},
live_decision_position_size=0.0`); `engine/pipeline.py WeightPipeline.run()` (+`_sanitize_weights`
NaN/inf/allow_short gate); `service.py StrategyService.evaluate(...,as_of)` (captures once per
run, 10-thread fan-out); `api.py StrategyAPI` (+`_precondition_dict` overlay
`{tested,precondition_held,last_checked_at}`); `clients/features_client.py` (forwards `as_of` →
`GET /features/{symbol}`), `correlation_client.py`; `storage/precondition_state.py
PreconditionStateStore` (upsert per strategy — never YAML); `server/routes_read.py`
(`GET /strategy/strategies`, `GET .../{name}` with overlay, `POST .../{name}/precondition-check`
404-guarded, `POST .../{name}/evaluate?symbols&as_of`, weights/runs/docs routes).
HOW: `POST .../evaluate` threads one `as_of` through service→features→tools→stock enforcement
(default now = unchanged callers). Precondition checked live by poller → write-back for EXECUTE+
SKIP (checked-and-failed still counts; EXTEND/error not).
SCENARIO: `POST sma_cross_live/evaluate?symbols=AAPL&as_of=<Tue close>` → all symbols share Tue
instant; must `{live_indicators,adx_14,gt,20}` evaluated; poller EXECUTE writes
`{tested:true,held:true}` overlaid on next GET (YAML untouched).

## 12. Portfolio risk — allocation with 4 tilts + two scalers + netting decision

WHERE: `vinu-portfolio/vinu_portfolio/service.py:992 compute_daily_allocation()`; tilts
`_regime_alignment/_outcome_confidence/_confidence_gradient/risk_mult` (`:715-734`);
`_drawdown_action_multiplier(ok1/halve.5/flat0/halt0)` + `_maturity_capital_multiplier()`
(`:880-928`); `_detect_not_funded()` via `record_rejection`; hysteresis
`MIN_WEIGHT_CHANGE=0.02`, action-cap `MAX_ACTION=0.20`, `cap_concentration(max_per_strategy_weight)`,
`max_correlated_cluster_weight=0.6`; `deployable_equity=equity×(1−reserve)×drawdown×maturity`;
response includes `weights,regime,sleeves,conflicts,not_funded,equity,reserve,deployable,drawdown,
risk_budget,maturity_multiplier`; `circuit_breakers.py compute_drawdown_action()` (pure) +
`PortfolioDrawdownMonitor.update/note_unavailable(3)/_halt_trading(POST .../broker/halt)`;
`risk_budget.py compute_risk_budget()` (`REGIME_MULT{bull1/bear.8/side.9/highvol.6}`,
tier warn−1%/reduce−2%/halt−3%); `research_link.py get_maturity_assessment()`; `config.py`
(`maturity_capital_gating_enabled=False`, mult cold0.1/paper0.25/early0.5/mature1.0,
`reserve_fraction=0.0`, halt−0.20, monitor 300s).
HOW: sleeves tilted → renormalized → hysteresis/caps → deployable scaled once (system-wide signal,
same mechanism as drawdown ladder; fails open 1.0). Net policy = net (only realizable
single-account; not duplicated in portfolio — would corrupt strategy-keyed tilts; severe →
`POST .../notify/symbol-conflict`).
SCENARIO: equity $100k, reserve 10%, drawdown ok(1.0), maturity early_live(0.5) → deployable
$45k; AAPL sleeve 0.10 tilted 1.1×risk0.9 → renormalized, capped, sized; unfunded candidate logged
with tilt-heuristic reason.

## 13. Live execution — scheduler + netting + breaker + VWAP/TWAP + reconciliation

WHERE: `vinu-live/vinu_live/scheduler.py:64 LiveScheduler.cycle(:127)` (portfolio → live-decision
weights → `SignalTranslator.translate` → `_check_breaker` → `_plan_execution/_execute_plan` →
`reconcile` → drift); `_check_breaker(:245)` (BookBackend+BreakerState, `covariance=None` skips
agg-VaR only, fresh HALT → `_engage_real_halt POST .../broker/halt`); `_maturity_scaled_limits
(:218)` (opt-in `risk_gatekeeper_maturity_scaling_enabled`, `maturity_link scale_limits_for_tier
{cold.25/paper.5/early.75/mature1.0}` floored, logged to `MaturityConsultationStore`);
`signal_translator.py _net_by_symbol` (sums, opposite-sign warning; fail-closed on missing price);
`execution.py plan_twap(n=6)/plan_vwap/volume_profile/schedule_delays`; `reconciliation.py
ReconciliationEngine` (`{drift,symbol_drifts,total_drift_pct}`); `_handle_reconciliation_drift`
+ `_notify_target_weight_drift` (`RECON_DRIFT_ALERT_CYCLES=3`, edge-triggered — same-cycle
target-vs-prefill gap is expected, not alerted); `breaker/engine.py:139 check_limits()`
(daily-loss/VaR/count/cluster/leverage), `breaker/limits.py DEFAULT_LIMITS`; `config.py`
(research URL, twap, slices); `server/app.py` (`POST /live/cycle`, trade-plan/feedback/shadow/
rebalance/emergency routes, `GET /live/status|decision-context|decisions|snapshots|tca/slippage`);
`entrypoint.sh` (worker+trade-plan+feedback+shadow+approval+live-decision workers, serve :8091).
HOW: every cycle risk-checked (was never called — CRITICAL fixed), netted (was whipsaw — fixed),
drift-streaked (was computed-never-alerted — fixed).
SCENARIO: AAPL target 0.02 + strategy-B short −0.01 → net 0.01 → breaker scaled 0.25× at
cold_start allows → TWAP 6 slices → reconcile finds 3-cycle 2% drift → notify once.

## 14. Live-decision loop — candle-close to order + review + snapshots

WHERE: `live_decision/poller.py:55 CandleClosePoller.cycle(:99)` (group by (ticker,timeframe),
cursor, bars, snapshot, move, evaluate, advance, review); `detector.py compute_live_snapshot`
(51 indicators via blessed `apply_indicators` + dist/boll/macd-hist/vwap-dist),
`min_warmup_bars()`, `detect_move(2.0×ATR)`; `state_tracker.py evaluate_candle_close`
(idle→fired_awaiting_confirmation→ready_to_execute→executed/expired) + `mark_executed(reason)`;
`storage.py LiveDecisionBackend(SCHEMA_VERSION=4)` (cursors, stages, transitions, `live_decisions`
incl error/unrecognized, `live_decision_open_positions` source of truth, `live_snapshots` +
`staleness_seconds`); `schema.py` (5 tables, Stage enum, records); `bars_client.py`
(`GET /stock/candles/{symbol}`); `conditions.py evaluate_all` (eq/neq/gt/gte/lt/lte/in/between,
AND) + `condition_name({source,key,operator,value})`; triggers `_trigger_live_decision (POST
.../agent/live-decision/run` once per fresh-ready, fail-logged retry), `_trigger_position_review
(mode=review cadence `review_cadence_bars=5`, HOLD keeps / EXIT→`close_position`→ next cycle omits
→ close-to-0 sells; REDUCE/ADD not built), `_record_precondition_check`,
`_detect_and_record_move (POST .../research/move-evidence)`,
`_record_signal_evidence_trigger (POST .../research/signal-evidence/trigger`,
auto-name `live_indicators.adx_14_gt_999`, once per genuine firing, best-effort);
`server/app.py` (`GET /live/decision-context`, `GET /live/decisions/...`,
`GET /live/snapshots/{symbol}[.../{angle}/history]`); `cli.py live-decision-worker`.
HOW: watermark on real latest bar (not clock — weekends/holidays safe); shared fetch per
(ticker,timeframe); open positions re-emitted every cycle from stored size (second-cycle
force-close bug fixed); review re-invokes SAME team in review mode (no 2nd agent).
SCENARIO: AAPL 15m close → snapshot adx 23 → must fires → grace → ready → `POST
/agent/live-decision/run` → EXECUTE (precondition-held true) → `live_decisions` row + open position
0.02 → scheduler emits 0.02 every cycle → 5 bars later review HOLD → stays; later EXIT → row closed
→ next cycle weight omitted → sold.

## 15. Deciding agent + context tool (in vinu-agent, not vinu-live)

WHERE: `teams/live_decision/agents/live_decision_agent/{AGENT.md,prompt.md}` (tools
`[get_live_decision_context,get_signal_evidence]`, no execution tool by omission; entry + review
sections); `tools/get_live_decision_context_tool.py` (fans out to live decision-context + strategy
+ past decisions + `get_signal_evidence` + `maturity_status` when
`live_decision_maturity_scaling_enabled` (opt-in, read-only context, never hard gate) via
`GET .../research/maturity/status`; logs to `MaturityConsultationStore`); `server/
routes_live_decision.py POST /agent/live-decision/run` (`{ticker,strategy_id,trigger_id,
mode=entry|review,position_context}` → `session/service.py run_team_once("live_decision")` via
`build_registry()+TeamManager`, `headless-{tag}-{uuid}`, `_extract_json_block`).
HOW: poller lives in live (needs candles), decider lives in agent (needs teams/LLM) — HTTP between
(point 8 built as designed). Past decisions composed in (anti-flip-flop prompt rule).
SCENARIO: agent receives `{stage:ready_to_execute, live_snapshot:{adx:23}, precondition:{defined:
true}, signal_evidence:{34 triggers,58%+}, past:[SKIP 2d ago "resistance"], maturity:{early_live}}`
→ returns `{"decision":"EXECUTE","precondition_held":true,...}`.

## 16. Adversarial debate + reflection synthesis consumer

WHERE: `swarm/presets/investment_committee.yaml` (bull→bear→risk(depends bull,bear));
`scheduler_workers.py _start_investment_committee_debate` (`create_run(investment_committee)`);
`routes_swarm.py` (`POST /swarm/runs`, `GET .../latest?preset&symbol`, `ensure-fresh`; `none`→
proceed — async/opt-in by instruction); `tools/reflection_synthesis_tool.py
GetReflectionSynthesisTool` (`GET ...:8092/reflection/synthesis/latest`, HTTP-only — no
in-process fallback, circular both directions); wired into research-team `idea_generator`
(Planner=`planner_worker_main` triage → `run_team_for_ticker("research")`; no single Planner
AGENT.md — documented honestly).
HOW: debate never blocks a trade; synthesis is advisory context for idea generation.
SCENARIO: idea generator reads `{profile:[Regime:degrading,...], suggestion:{...}}` (or
`{status:none}` — common, not error) before drafting AAPL variant.

## 17. Reflection brain — 24 analysts + 6-axis synthesis (read-only power)

WHERE: `vinu-reflection/vinu_reflection/cli.py reflection_worker_main/run_cycle` (5-min analysts, hourly
brain); 24 `reflection/*.py` (decision_process, process_mining, debate_value, angle_trust,
ingest_health, loss_attribution, memory_effectiveness, rebalance_bypass, event_holding_loss,
mandate_limit_friction, triage_freshness, regime_drift, significance_response_outcome,
dl_angle_backtest_health, shock_reading_before_halt, lesson_maturity_baseline_check (analysis T,
reads `_maturity_assessor.py` + `recent_form_reading` last-5), correlation_coverage,
paper_live_correlation, regime_strategy_coverage, skill_edit_governance, screener_agreement,
concentration_coverage, threshold_calibration, consistency_freeze); `reflection/brain.py`
(`gather_synthesis_inputs` notable/significant only — empty most cycles = bounded LLM;
`run_synthesis` one call, fails open to unwritten; `resolve_pending_syntheses` mechanical —
threshold_nudge checkable vs later beliefs, rest inconclusive; `CLUSTERS` 6 axes, `WINDOW=7d`);
`config.py` (`brain_synthesis_enabled=False`, `interval=3600`, `worker=300`, `:8092`);
`server/{app,routes_synthesis}.py` (`GET /reflection/synthesis/latest|pending`, writer-only
`run_synthesis`); `vinu-infra/reflection.py` (`ReflectionStore`, `reflection_beliefs`,
`reflection_synthesis_outcomes` 12-col exact, `write_finding` routine→None).
HOW: never orders / never kill-switch (`proposed_action` read-only); Hindsight unwired (zero
clients in code — v1 reads Layer-0 beliefs only, stated fallback not workaround).
SCENARIO: beliefs {degradation AAPL significant, correlation spike} → hourly brain writes one
6-axis profile + `watch_regime` suggestion → Planner reads it next cycle.

## 18. Maturity + evaluation visibility (one tier, one log, one status)

WHERE: `vinu-research/vinu_research/maturity_assessor.py assess()` (`cold/paper/early/mature`,
`MIN_PAPER_DAYS=5,MATURE_MIN=30 trades+2 regimes`) + `vinu-reflection/vinu_reflection/reflection/_maturity_assessor.py`
(+`brier_mean,live_fraction,recent_form`); `vinu-infra/maturity_consultation.py`
(`maturity_consultations{service,consumer,tier,action,scope,evidence}` — writers:
live `_maturity_scaled_limits` + agent context tool); `vinu-infra/strategy_evaluation.py`
(`strategy_evaluation_history/status/step_registry`, 10 `STEP_DEFINITIONS`, `seed_step_registry`)
+ `GET /research/evaluation-status/{id}|/by-ticker/{ticker}|/evaluation-history/{id}`;
`vinu-portfolio/vinu_portfolio/research_link.py get_maturity_assessment()`.
HOW: tier computed twice deliberately (different dep directions, same logic, documented in
docstrings); consulted as input (prompt block / limit scaler / capital multiplier / review
context), never as manager; every consultation logged once, queryable everywhere.
SCENARIO: `GET /research/maturity/status` → `{tier:early_live, n_real:12, paper_days:9,
acc:0.58, regimes:[bull]}` → live scales limits 0.75× (logged), portfolio scales deployable 0.5×
(logged), agent shows tier to reviewer (logged) — three rows, one table.

## 19. Safety nets — kill switch, approval, audit, uncertainty

WHERE: portfolio `circuit_breakers._halt_trading` + `drawdown_scheduler monitor_main_loop`
(`GET .../broker/account` → `update()` → halt + `DrawdownStatusStore`); live `_check_breaker` +
`_engage_real_halt`; `trade_plan_approval_worker`; `trade_audit_log.py` + run cards +
`live_decisions` + `sweep_runs/points` + `generation_rounds/candidates` + `maturity_consultations`
+ `evaluation_history`; agent `CallCache` (instance-lifetime, errors/empties never cached),
`_date_utils` (UTC-aware), tool as-of clamps (client 2nd layer, untested per #11.2 — server is
1st layer now); `GET /trace/{ref_id}`, `GET /research/evaluation-status/*` ("why isn't this
trading" single view).
HOW: AI cannot override halt; halts cross-process via `POST .../broker/halt`; uncertainty has no
single score — gates + shared status view instead (honest partial).
SCENARIO: daily loss −6% vs limit −5% → `HALT` → all cycles refuse → `GET evaluation-status/AAPL`
shows `risk_gatekeeper:HALT (daily-loss)` as the blocking step.

## 20. End-to-end AAPL story (one scenario tying 1–19)

Seed ranker ranks AAPL #7 (XYZ-IPO rejected for history) → planner-worker cycle (screener∩store)
triages AAPL (K-cap free) → research idea "SMA crossover" deduped to existing hypothesis →
prompt includes 12-trigger/58% reasoning + synthesis profile + maturity early_live → 3 drafts,
winner researched, all recorded → grid 12 points, winner (5,50) kept with 11 loser reasons →
backtest (regime 0.7×) Sharpe 1.4 → hypothesis evidence appended (signal kind, no promotion) →
TradeScore 109 moderate ×0.7, R:R 2.1 passes → plan authored (maturity block) → strategy evaluate
`as_of` → weights → portfolio tilts, deployable 0.5×, netted → live cycle: breaker scaled 0.75×
allows, TWAP 6 slices, reconciled → candle-close fires must → context tool composes stage+snapshot+
precondition+34-trigger history+past SKIP+maturity → EXECUTE → open position 0.02 → re-emitted
each cycle → 5-bar review HOLD → thesis decays (score 82→41) → EXIT → sold → outcome recorded →
decay/brain notice → graveyard + beliefs updated → next idea avoids repeat.

---

## Stale-cross-check (old claims → current truth)

- "28/29 angles" → 30 `*/compute.py` (35 dir entries). "Maturity prompt-only" → + risk + capital +
  live-decision consults + shared log. "No exit" → HOLD/EXIT review + open-positions table.
- "Seed-only tickers" → live intersection when configured. "No graveyard" → read-time union +
  route. "No precondition write-back" → store + route + poller writer. "Sweep losers lost" →
  `sweep_grid_points` keeps all. "No generation record" → rounds/candidates + routes.
- Still honestly open: agent↔research stamp; blessed-path enforcement; `trade_plan_tool` coverage;
  single uncertainty score; mandatory debate (declined); REDUCE/ADD; P&L-for-reviewer (needs bucket
  table); code_hash→sweep join; graveyard-as-gate; other-route `as_of`; full 30-angle live snapshots;
  evidence_triggers wiring; risk/capital synthesis consumers; Layer-2 qualitative maturity LLM;
  narrating agent; bucket table (deferred until real rows — agent uses raw counts + qualitative note).
- Deferred by decision: L2 depth (paid tier), on-chain (no consumer).

Recheck 1 (structure): 20 sections, every vision A1–A18 + B1–B13 mapped. Recheck 2 (code): every
file:line above re-opened 2026-09-30; no doc-only claims.

## Appendix: empty-meaning contract (C5 fix, 2026-09-30)

No behavior changed — this only writes down what each empty already means, in one place, so no
caller mistakes "no rows" for "not yet run". Canonical source:
`vinu-research/.../server/routes_introspect.py` module docstring; contract tests:
`vinu-research/tests/test_empty_meanings.py`.

- `outcome_status`: `passed` (best result exists) / `no_strategy_found` (stopped, no best, no
  infra signal — genuine, not error) / `infra_failure` (last reasoning carries INFRASTRUCTURE
  FAILURE prefix — retry later, not a verdict).
- Per-candidate backtest `None`: that candidate raised; rest still rank. All-`None` + recorded
  exception → re-raises (real errors surface, never silent empties).
- Sweep all-points-failed: `ranked=[]`, `completeness=0.0`, `pbo=None`, `walk_forward=None`
  (skipped). Empty grid itself is a ValueError, not an empty result.
- `sweep_id=""`: not persisted (`persist=False` or persist-write failed — sweep still returned);
  uuid → row exists in `sweep_grid_points`.
- Walk-forward `None`: skipped (disabled/empty ranked) or zero completed windows.
- Generation store `None`/disabled: round not recorded, generation unaffected (deliberate no-op).
- Eval artifact `404`: never evaluated ("none on file", expected). By-ticker `count=0`: nothing
  evaluated (not an error). Agent eval context `""`: env unset or nothing to report (prompt
  byte-identical without it).
- Paper-return statuses (`no_strategy_code_or_universe`, `backtest_failed: …`,
  `backtest_returned_none`, `no_returns`): degraded diagnostics, `daily_return=None`, never crash.

Agent mapping rule: empties → WAIT (nothing yet) or DONE (genuinely nothing); only raised
exceptions and transport errors → ERROR.
