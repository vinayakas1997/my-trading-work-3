Confirmed. I now have everything needed for a complete, verified report.

vinu-components: Verified Service & Inter-Service Call Map
All data below verified by reading docker-compose.yml and actual source (httpx/requests call sites), not docs.

1. Services, Ports, Health Endpoints
Service (compose name)	Package	Host:Port mapping	Container port	Health check path (from healthcheck block)
news-api	vinu-news	127.0.0.1:8080	8080	GET /news/health
stock-api	vinu-stock-price	127.0.0.1:8081	8081	GET /stock/health
features-api	vinu-tools	127.0.0.1:8082	8082	GET /features/health
initial-analysis-api	vinu-initial-analysis	127.0.0.1:8083	8083	GET /analysis/health
quant-core-api	vinu-strategy + vinu-simulator (merged, vinu_strategy/server/merged_app.py)	127.0.0.1:8084	8084	GET /strategy/health and GET /simulator/health (both checked)
agent-api	vinu-agent	127.0.0.1:8086	8086	GET /agent/health
research-api	vinu-research	127.0.0.1:8087	8087	GET /research/health
portfolio-api	vinu-portfolio	127.0.0.1:8090	8090	GET /portfolio/health
live-api	vinu-live	127.0.0.1:8091	8091	GET /live/health
Note: vinu-strategy and vinu-simulator are not separate compose services — both are mounted in one FastAPI app (merged_app.py) with include_router(..., prefix="/strategy") and include_router(..., prefix="/simulator"), served together on port 8084 as quant-core-api.

Background workers (non-HTTP-server processes started by entrypoint.sh, same container):

agent-api: serve (FastAPI) + skill-audit-worker + planner-worker + significance-worker
live-api: serve (FastAPI) + vinu-live-worker (portfolio rebalance, LiveScheduler.cycle) + trade-plan-worker (TradePlanOrchestrator.cycle) + feedback-worker (FeedbackLoopWorker.cycle) + shadow-worker (ShadowEvaluator.evaluate_all)
portfolio-api: FastAPI + in-process drawdown monitor scheduler (drawdown_scheduler.py)
news-api, stock-api, features-api, initial-analysis-api, research-api: each also runs an ingest/compute background worker per the compose comments (worker internals not expanded here — out of scope for cross-service calls beyond what's below).
2. Dependency Graph (depends_on, all condition: service_healthy)

news-api            -> (none)
stock-api           -> (none)
features-api        -> stock-api
initial-analysis-api-> news-api, stock-api
quant-core-api      -> features-api, initial-analysis-api, stock-api
research-api        -> features-api, quant-core-api, initial-analysis-api, stock-api
portfolio-api       -> quant-core-api, research-api
agent-api           -> stock-api, features-api, news-api, initial-analysis-api, quant-core-api, research-api
live-api            -> portfolio-api, agent-api, stock-api
Mermaid-ready edge list (A --> B = A depends_on B):


features-api --> stock-api
initial-analysis-api --> news-api
initial-analysis-api --> stock-api
quant-core-api --> features-api
quant-core-api --> initial-analysis-api
quant-core-api --> stock-api
research-api --> features-api
research-api --> quant-core-api
research-api --> initial-analysis-api
research-api --> stock-api
portfolio-api --> quant-core-api
portfolio-api --> research-api
agent-api --> stock-api
agent-api --> features-api
agent-api --> news-api
agent-api --> initial-analysis-api
agent-api --> quant-core-api
agent-api --> research-api
live-api --> portfolio-api
live-api --> agent-api
live-api --> stock-api
3. Real Outbound HTTP Calls, by Caller Service
Env var → target service resolution (from .env-example, matches every service's config.py):
VINU_STOCK_API_URL/VINU_STOCK_PRICE_API_URL→stock-api:8081, VINU_NEWS_API_URL→news-api:8080, VINU_FEATURES_API_URL/VINU_TOOLS_API_URL→features-api:8082, VINU_CORRELATION_API_URL/VINU_INITIAL_ANALYSIS_API_URL→initial-analysis-api:8083, VINU_STRATEGY_API_URL/VINU_SIMULATOR_API_URL→quant-core-api:8084, VINU_AGENT_API_URL→agent-api:8086, VINU_RESEARCH_API_URL→research-api:8087, VINU_PORTFOLIO_API_URL→portfolio-api:8090, VINU_LIVE_API_URL→live-api:8091.

stock-api
No outbound calls to any other vinu-* service found (leaf node; only external market-data providers in vinu-stock-price, not applicable here).

news-api
vinu_news/service.py _stock_client() → vinu_news/integrations/stock_price.py:StockPriceClient → stock-api GET /stock/candles/{symbol} (or similar, via fetch_candles). Trigger: _enrich_with_price_reaction() — enriching stored articles with post-publish price reaction.
features-api (vinu-tools)
vinu_tools/engine/engine.py → client/stock_price.py:StockPriceClient.fetch_candles → stock-api GET /stock/candles/{symbol}. Trigger: background feature-compute engine building indicators for a symbol.
vinu_tools/server/routes_features.py:get_feature_or_symbol() (GET /features/{symbol_or_kind}) → stock-api GET /stock/candles/{symbol}?days=60[&indicators=...], with retry loop (_REATTEMPTS). Trigger: caller requests a symbol (not a known indicator kind) so the route live-fetches candles to compute values on the fly.
vinu_tools/service.py:health_info() → stock-api GET /stock/health (health/dependency probe only, 3 retries).
initial-analysis-api
vinu_initial_analysis/clients/news_client.py:NewsClient → news-api: GET /news/articles/since, GET /news/ticker/{symbol} (two call sites: get_ticker_news, differing params).
vinu_initial_analysis/clients/price_client.py:PriceClient → stock-api: GET /stock/watchlist/tickers, GET /stock/candles/{symbol}.
Callers of these clients (runner.py:_price_client.get_candles/_news_client.get_ticker_news, plus angles/news_price_causality/compute.py, angles/news_price_causality/impact.py, angles/peer_relative_strength/compute.py, angles/shock_clustering/compute.py): the "angle" compute engines that run per-symbol analysis (triggered by the /analysis/run/{symbol} route or scheduled recompute).
quant-core-api (strategy side, vinu_strategy)
vinu_strategy/clients/features_client.py:FeaturesClient.get_features → features-api GET /features/{symbol}. Trigger: StrategyService.evaluate() (POST /strategy/strategies/{name}/evaluate) building per-symbol indicator context.
vinu_strategy/clients/correlation_client.py:CorrelationClient → initial-analysis-api: GET /analysis/impact/{symbol}, GET /analysis/correlation/{symbol}, GET /analysis/drawdown/{symbol}, GET /analysis/angle/{angle_name}/{symbol}. Trigger: same StrategyService.evaluate() call, fetching correlation/angle context for the strategy's required angles.
quant-core-api (simulator side, vinu_simulator)
vinu_simulator/clients/strategy_client.py:StrategyClient → quant-core-api itself (self-referential network hop: VINU_STRATEGY_API_URL defaults to the same host:8084) GET /strategy/weights, GET /strategy/runs, GET /strategy/strategies. Trigger: SimulatorService backtest run (get_weights called inside the run-backtest path, ~service.py:106).
vinu_simulator/clients/price_client.py:PriceClient → stock-api GET /stock/candles/{symbol} (via get_ohclv/get_price_and_volume). Trigger: same backtest run, fetching price/volume for the strategy's tickers.
vinu_simulator/clients/features_client.py:FeaturesClient → features-api GET /features/indicators/{symbol}.
research-api
All via vinu_research/tools.py:ResearchTools (ResilientClient, per-service base URL includes route prefix already):

→ quant-core-api (simulator side): POST /simulator/simulate/custom (run_backtest), GET /simulator/results/{run_id}/equity (fetch_equity_returns), GET /simulator/results/{run_id}/weights (fetch_weights).
→ initial-analysis-api: GET /analysis/story/{symbol} (get_story), GET /analysis/drawdown/{symbol} (get_drawdowns), GET /analysis/correlation/{symbol} (get_correlation), GET /analysis/angle/{angle_name}/{symbol} (get_angle_rows, called 4x in parallel by get_angle_context for trend_lifecycle/trend_session_structure/news_price_causality/backtesting_44_metrics).
→ features-api: GET /features/{symbol} (get_feature_snapshot).
→ stock-api: GET /stock/candles/{symbol} (get_benchmark_data).
vinu_research/scheduled/executor.py (decay/regime-recompute scan, background worker) → initial-analysis-api POST /analysis/run/{symbol}?angle_names=regime_analysis (regime_recompute_scan, one call per symbol in ACTIVE/MONITORING artifacts).
vinu_research/service.py:health() → fan-out health probe: quant-core-api GET /simulator/health, features-api GET /features/health, initial-analysis-api GET /analysis/health (dependency-reachability check on research-api's own /research/health).
portfolio-api
All in vinu_portfolio/service.py (httpx.AsyncClient) unless noted:

→ quant-core-api: GET /strategy/strategies (_list_yaml_strategies, in list_active_strategies); GET /simulator/results/{artifact_id}/equity (_fetch_strategy_returns, in compute_correlation_matrix/build_portfolio).
→ research-api: GET /research/artifacts (_list_llm_strategies); GET /research/trade-plan/{artifact_id}/calibration (_fetch_outcome_confidence); GET /research/trade-plan/{artifact_id} (_fetch_trade_plan).
→ stock-api: GET /stock/candles/{benchmark_symbol} (_fetch_benchmark_regime); also historical_simulation.py → GET /stock/candles/{symbol} (historical regime-tilt simulation).
→ agent-api: GET /agent/broker/account (_fetch_account_equity); GET /agent/broker/positions (_fetch_positions).
vinu_portfolio/drawdown_scheduler.py (background monitor loop) → agent-api GET /agent/broker/account (run_once, polls equity each interval).
vinu_portfolio/circuit_breakers.py → agent-api POST /agent/broker/halt (fired when a drawdown breach crosses _threshold).
live-api
vinu_live/feedback_loop.py (FeedbackLoopWorker.cycle, background) →
research-api: POST /research/trade-plan/{artifact_id}/record-outcome (_record_calibration_outcome); GET /research/hypotheses (_record_hypothesis_evidence, listing); POST /research/hypotheses/{hypothesis_id}/evidence (same fn, writing).
initial-analysis-api: POST /analysis/pnl-attribution/{symbol}/record (_push_pnl_attribution); POST /analysis/run/{symbol} (_refresh_personality_stats).
agent-api: POST /agent/ticker-ledger/event (_write_ticker_ledger_closeout).
vinu_live/shadow_evaluator.py (ShadowEvaluator.evaluate_all, background) → research-api: GET .../ for benching artifacts (_list_benching_artifacts, line ~52), GET .../ for sharpe (_fetch_paper_sharpe, line ~110), agent-api: POST .../ promotion call (_promote_artifact, line ~132) — constructed from research_api_url/agent_api_url passed into ShadowEvaluator.__init__.
vinu_live/trade_plan/orchestrator.py (TradePlanOrchestrator.cycle, background) →
research-api: GET /research/artifacts (_fetch_active_trade_plans); GET /research/trade-plan/{artifact_id} (same fn); GET /research/trade-plan/{artifact_id}/calibration (_fetch_calibration_accuracy).
agent-api: POST /agent/broker/order (_submit_order); GET /agent/broker/account (_fetch_portfolio_value); GET /agent/broker/positions (_fetch_broker_positions).
stock-api: GET /stock/candles/{symbol} (_fetch_prices, _fetch_recent_prices).
initial-analysis-api: GET /analysis/angle/shock_clustering/{symbol} (_fetch_shock_cluster_correlation).
vinu_live/scheduler.py (LiveScheduler.cycle, background portfolio-rebalance worker) →
portfolio-api: GET /portfolio/state (_fetch_portfolio).
agent-api: GET /agent/broker/positions (_fetch_positions); GET /agent/broker/account (_fetch_portfolio_value); POST /agent/broker/order (_execute_plan).
stock-api: GET /stock/candles/{symbol} (_fetch_prices, _fetch_volume_weights).
agent-api (vinu-agent) — every real tool/hook that makes a cross-service call
Tool name → target service → endpoint (all resolve base URL via self._services_config.get("vinu_X", default), i.e. the services dict built from VINU_*_API_URL in config.py):

Tool / component (file)	Target service	Call
run_strategy (strategy_tool.py)	quant-core-api	POST /strategy/strategies/{name}/evaluate?symbols={symbol}
list_strategies (list_strategies_tool.py)	quant-core-api	GET /strategy/strategies
run_backtest (backtest_tool.py)	quant-core-api	POST /simulator/simulate/custom
factor_analysis (factor_analysis_tool.py)	none — in-process import of vinu_tools.compute.registry/alpha_meta, not an HTTP call	
factor_backtest (factor_backtest_tool.py)	stock-api	GET /stock/candles/{symbol}
get_backtest_validation (backtest_validation_tool.py)	quant-core-api	GET /simulator/results/{run_id}
get_features (features_tool.py)	features-api	POST /features/requests then GET /features/requests/{request_id}/data (async job pattern)
list_available_features (list_features_tool.py)	features-api	GET /features/catalog, GET /features/presets
get_stock_price (stock_price_tool.py)	stock-api	GET /stock/candles/{symbol}
get_news (news_tool.py)	news-api	GET /news/ticker/{symbol}
get_correlation (correlation_tool.py)	initial-analysis-api	GET /analysis/correlation/{symbol}
get_all_angles (angles_tool.py)	initial-analysis-api	GET /analysis/angles, GET /analysis/angle/{name}/{ticker}
list_research_runs (list_research_runs_tool.py)	research-api	GET /research/runs
find_trade_plan_artifact (find_trade_plan_tool.py)	research-api	GET /research/artifacts?type_=trade_plan
create_hypothesis/add_hypothesis_evidence (hypothesis_write_tools.py)	research-api	POST /research/hypotheses; POST /research/hypotheses/{id}/evidence
query_hypotheses (query_hypotheses_tool.py)	research-api	GET /research/hypotheses
run_research (research_tool.py)	research-api	POST /research/run
get_run_checkpoints (run_checkpoints_tool.py)	research-api	GET /research/runs/{run_id}/checkpoints
run_parameter_sweep (run_parameter_sweep_tool.py)	research-api	POST /research/sweep/grid
run_sweep_candidate/list_sweep_recipes (run_sweep_candidate_tool.py)	research-api	POST /research/sweep/candidate; GET /research/sweep/recipes
check_symbol_research_state (symbol_research_state_tool.py)	research-api	GET /research/symbols/{symbol}/state
submit_thesis (submit_thesis_tool.py)	research-api	in-process dedup read, HTTP fallback GET /research/hypotheses?symbol=; then POST /research/hypotheses/human
get_trade_plan_calibration (trade_plan_calibration_tool.py) + list_active_artifacts_for_rebalance (rebalance_context_tool.py)	research-api	via agent/trade_plan_calibration.py:get_trade_plan_calibration() — in-process read, HTTP fallback GET /research/trade-plan/{artifact_id}/calibration
compute_allocation_candidates (allocation_tool.py)	portfolio-api	POST /portfolio/evaluate-batch
list_portfolio_strategies (list_portfolio_strategies_tool.py)	portfolio-api	GET /portfolio/strategies
get_portfolio_concentration (portfolio_concentration_tool.py)	portfolio-api	GET /portfolio/state
compare_portfolio (portfolio_comparison_tool.py)	portfolio-api, research-api	GET {portfolio_api}/state; artifacts: in-process read, HTTP fallback GET {research_api}/artifacts — both fallback URLs are missing their /portfolio and /research route prefixes (see note below), unlike the primary paths above
generate_trade_plan (trade_plan_tool.py)	initial-analysis-api, features-api, quant-core-api, stock-api, news-api, research-api	GET /analysis/symbols; GET /analysis/angle/{name}/{symbol}; POST /features/requests; GET /simulator/runs?symbol=; GET /simulator/results/{run_id}; GET /stock/candles/{symbol}; GET /news/search; GET /research/artifacts; GET /research/trade-plan/{symbol}; POST /research/hypotheses
HttpRunLogReader (agent/ticker_gate.py, used by planner-worker)	initial-analysis-api	GET /v1/stage1/vinu-initial-analysis/latest-run/{ticker}
agent/significance_triage.py (significance-worker)	research-api	POST /research/hypotheses/{hypothesis_id}/evidence
apply_capital_allocator_decision (agent/capital_allocator_hook.py)	live-api	POST /live/trade-plan/rebalance-request
audit/ground_truth.py, audit/research_digest.py	research-api	base URL resolved (self._services_config.get("vinu_research")); specific paths not further traced here — read the files directly for exact routes if needed
audit/freshness.py	initial-analysis-api	GET /analysis/angle/{angle}/{symbol}
broker/order_guard.py	portfolio-api	GET /portfolio/state (pre-trade guard check)
broker/historical_broker.py	stock-api	GET /stock/candles/{symbol} (paper/historical fill simulation)
memory/sync_service.py (SyncService) — appears unwired: no caller found anywhere in the codebase outside its own tests	research-api, quant-core-api, stock-api, news-api	in-process reads with HTTP fallback: GET {url}/runs (research), GET {url}/artifacts (research), GET {url}/runs (simulator), GET {url}/candles/{symbol} (stock), GET {url}/search (news) — all fallback paths are missing their route prefixes (/research, /simulator, /stock, /news), same pattern as portfolio_comparison_tool.py above
Note on the two flagged rows: every service mounts its routes under a prefix (confirmed e.g. vinu-portfolio/vinu_portfolio/server/app.py:36: APIRouter(prefix="/portfolio")). Most agent-side HTTP call sites correctly include that prefix in the path they request (e.g. list_research_runs_tool.py → GET {url}/research/runs). But the HTTP-fallback-only branches in sync_service.py and portfolio_comparison_tool.py._fetch_artifacts/_fetch_portfolio build the request path without the prefix (e.g. GET {url}/runs instead of GET {url}/research/runs), which would 404 against the real server if that fallback path were ever exercised. Worth calling out in the doc as a latent inconsistency rather than a documented API.