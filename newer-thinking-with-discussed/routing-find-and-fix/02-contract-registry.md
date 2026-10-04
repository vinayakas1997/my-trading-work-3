# Contract registry (GENERATED — do not edit by hand)

Produced by `python -m vinu_infra.contract_scan`. Producers = the real OpenAPI of every service app; consumers = every
HTTP call found in the source. Re-run it after any route or caller change; `contracts.json` next to this file is the
machine-readable copy.

- Services read: 13 of 13
- Routes: 272; HTTP calls found in source: 183; calls matched to a route: 177
- Findings: 1 ERROR, 0 WARN (see `03-findings.md` for what each means and its fix status)

Legend: `*` = required. Body `(open)` = untyped object, any key accepted. Callers are `file:line`.

## agent

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /agent/admin/settings` | - | - | **nobody** |
| `PATCH /agent/admin/settings` | - | (open) | **nobody** |
| `GET /agent/admin/settings/schema` | - | - | **nobody** |
| `POST /agent/admin/settings/{name}/reset` | - | - | **nobody** |
| `GET /agent/broker/account` | - | - | live; portfolio |
| `GET /agent/broker/asset/{symbol}` | - | - | live |
| `POST /agent/broker/halt` | - | scope, reason | live; portfolio |
| `GET /agent/broker/limits` | - | - | **nobody** |
| `DELETE /agent/broker/limits/{symbol}` | - | - | **nobody** |
| `GET /agent/broker/limits/{symbol}` | - | - | **nobody** |
| `PUT /agent/broker/limits/{symbol}` | - | max_order_value, max_position_pct, max_capital_utilization_pct, reason, set_by | **nobody** |
| `GET /agent/broker/limits/{symbol}/history` | limit | - | **nobody** |
| `GET /agent/broker/mandate` | - | - | **nobody** |
| `POST /agent/broker/mandate/renew` | - | days, until | **nobody** |
| `POST /agent/broker/order` | - | symbol*, side*, qty*, order_type, limit_price, stop_price, time_in_force, take_profit_price, stop_loss_price, stop_loss_limit_price, reduce_only, client_order_id | live |
| `GET /agent/broker/order/{order_id}` | - | - | live |
| `GET /agent/broker/overrides` | - | - | **nobody** |
| `DELETE /agent/broker/overrides/{symbol}` | - | - | **nobody** |
| `PUT /agent/broker/overrides/{symbol}` | - | state*, reason, set_by | **nobody** |
| `GET /agent/broker/performance/{artifact_id}` | - | - | live; research |
| `POST /agent/broker/performance/{artifact_id}` | - | daily_returns* | **nobody** |
| `POST /agent/broker/performance/{artifact_id}/append` | - | daily_return*, trade_date* | live |
| `GET /agent/broker/positions` | - | - | live; portfolio; screener |
| `POST /agent/broker/resume` | - | scope | live |
| `GET /agent/broker/safety-ledger` | limit | - | **nobody** |
| `GET /agent/broker/status` | scope | - | live |
| `GET /agent/health` | - | - | **nobody** |
| `POST /agent/live-decision/run` | - | ticker*, strategy_id*, trigger_id, mode, position_context, novelty | live |
| `POST /agent/notify/reconciliation-drift` | - | symbol*, action*, book_qty, broker_qty, expected_qty, actual_qty, drift_pct, detail | live |
| `POST /agent/notify/symbol-conflict` | - | symbol*, contributions*, net_weight*, gross_weight*, severity* | portfolio |
| `POST /agent/notify/trade-plan-pending` | - | artifact_id*, symbol*, reasons | live |
| `GET /agent/options/{symbol}/snapshot` | expiration, limit | - | research |
| `GET /agent/sessions` | limit | - | **nobody** |
| `POST /agent/sessions` | - | title, as_of | **nobody** |
| `DELETE /agent/sessions/{session_id}` | - | - | **nobody** |
| `GET /agent/sessions/{session_id}` | - | - | **nobody** |
| `POST /agent/sessions/{session_id}/cancel` | - | - | **nobody** |
| `GET /agent/sessions/{session_id}/events` | last_event_id | - | **nobody** |
| `GET /agent/sessions/{session_id}/messages` | limit | - | **nobody** |
| `POST /agent/sessions/{session_id}/messages` | - | content*, as_of | **nobody** |
| `GET /agent/status` | - | - | **nobody** |
| `GET /agent/swarm/presets` | - | - | **nobody** |
| `POST /agent/swarm/runs` | - | preset_name*, user_vars* | **nobody** |
| `POST /agent/swarm/runs/ensure-fresh` | max_age_minutes, preset_name*, symbol* | - | live |
| `GET /agent/swarm/runs/latest` | preset_name*, symbol* | - | research |
| `GET /agent/swarm/runs/{run_id}` | - | - | **nobody** |
| `POST /agent/swarm/runs/{run_id}/cancel` | - | - | **nobody** |
| `POST /agent/ticker-ledger/event` | - | ticker*, stage*, event_type*, text, ref_id, source | live |
| `GET /agent/trace/{ref_id}` | - | - | **nobody** |

## initial-analysis

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /analysis/angle/{angle_name}/{ticker}` | granularity | - | agent; live; research |
| `GET /analysis/angles` | active | - | agent |
| `GET /analysis/correlation/batch` | from_ts, symbols*, to_ts | - | **nobody** |
| `GET /analysis/correlation/{ticker}` | from_ts, to_ts | - | agent; research |
| `GET /analysis/coverage/{ticker}` | - | - | **nobody** |
| `GET /analysis/drawdown/{ticker}` | from_ts, to_ts | - | research |
| `GET /analysis/events/{ticker}` | from_ts, to_ts | - | **nobody** |
| `GET /analysis/health` | - | - | **nobody** |
| `GET /analysis/impact/{ticker}` | from_ts, to_ts | - | **nobody** |
| `GET /analysis/manifest` | - | - | **nobody** |
| `POST /analysis/pnl-attribution/{ticker}/record` | - | closed_positions* | live |
| `GET /analysis/run/jobs/{job_id}` | - | - | **nobody** |
| `POST /analysis/run/{ticker}` | angle_names, background, from_ts, to_ts | - | live; research |
| `GET /analysis/settings` | - | - | **nobody** |
| `GET /analysis/story/{ticker}` | from_ts, to_ts | - | research |
| `GET /analysis/symbols` | - | - | agent |
| `GET /v1/stage1/vinu-initial-analysis/factsheet/{ticker}/{method}` | tier | - | **nobody** |
| `GET /v1/stage1/vinu-initial-analysis/fetch/{ticker}/{granularity}/{time_range}/{method}` | - | - | **nobody** |
| `GET /v1/stage1/vinu-initial-analysis/fetch/{ticker}/{granularity}/{time_range}/{method}/{run_id}` | - | - | **nobody** |
| `GET /v1/stage1/vinu-initial-analysis/latest-run/{ticker}` | - | - | agent |
| `POST /v1/stage1/vinu-initial-analysis/trigger/{ticker}/{granularity}/{time_range}/{method}` | - | - | **nobody** |

## live

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /live/admin/settings` | - | - | **nobody** |
| `PATCH /live/admin/settings` | - | (open) | **nobody** |
| `GET /live/admin/settings/schema` | - | - | **nobody** |
| `POST /live/admin/settings/{name}/reset` | - | - | **nobody** |
| `POST /live/cycle` | - | - | **nobody** |
| `GET /live/decision-context/{ticker}/{strategy_id}` | - | - | **nobody** |
| `GET /live/decisions/needs-sizing` | limit | - | **nobody** |
| `GET /live/decisions/{ticker}/{strategy_id}` | limit | - | **nobody** |
| `GET /live/executions` | limit, symbol | - | **nobody** |
| `POST /live/feedback/cycle` | - | - | **nobody** |
| `GET /live/health` | - | - | **nobody** |
| `GET /live/lockouts` | - | - | **nobody** |
| `POST /live/shadow-evaluate` | - | - | **nobody** |
| `GET /live/snapshots/{symbol}` | - | - | **nobody** |
| `GET /live/snapshots/{symbol}/{angle_name}/history` | limit | - | **nobody** |
| `GET /live/status` | - | - | **nobody** |
| `GET /live/tca/slippage` | symbol | - | **nobody** |
| `POST /live/trade-plan/cycle` | - | - | **nobody** |
| `POST /live/trade-plan/emergency-flatten` | - | reason | **nobody** |
| `POST /live/trade-plan/emergency-resume` | - | reason | **nobody** |
| `GET /live/trade-plan/emergency-status` | - | - | **nobody** |
| `POST /live/trade-plan/rebalance-request` | - | symbol*, reason*, critical | agent |

## models

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `POST /models/angle/{angle}/compute` | - | symbol*, bars, news, from_ts, to_ts, time_format | **nobody** |
| `GET /models/angles` | - | - | **nobody** |
| `POST /models/finbert/score` | - | texts*, batch_size | **nobody** |
| `GET /models/health` | - | - | **nobody** |
| `GET /models/status` | deep | - | **nobody** |

## news

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /news/articles/since` | limit, ts* | - | **nobody** |
| `GET /news/backfill/job/{job_id}` | - | - | **nobody** |
| `GET /news/backfill/status` | - | - | **nobody** |
| `POST /news/backfill/trigger` | ticker | - | **nobody** |
| `POST /news/backfill/{ticker}/toggle` | - | enabled* | **nobody** |
| `GET /news/feeds` | all | - | **nobody** |
| `PATCH /news/feeds/{feed_id}` | - | enabled* | **nobody** |
| `POST /news/finbert/backfill` | batch_size | - | **nobody** |
| `GET /news/finbert/job/{job_id}` | - | - | **nobody** |
| `GET /news/health` | - | - | **nobody** |
| `GET /news/high-impact` | hours, limit, sentiment | - | **nobody** |
| `POST /news/ingest/ticker-news` | days | - | **nobody** |
| `POST /news/ingest/trigger` | - | - | **nobody** |
| `GET /news/latest` | date, limit, provider, tiers | - | **nobody** |
| `GET /news/poll/status` | - | - | **nobody** |
| `GET /news/providers` | - | - | **nobody** |
| `PATCH /news/providers/{provider_id}` | - | enabled* | **nobody** |
| `GET /news/search` | limit, q* | - | agent |
| `GET /news/settings` | - | - | **nobody** |
| `PATCH /news/settings` | - | mode, poll_interval_sec, active_tiers, backfill_start_date, backfill_pause_on_error | **nobody** |
| `GET /news/stats/ticker/{symbol}` | days | - | **nobody** |
| `GET /news/threads/active` | hours, limit | - | **nobody** |
| `GET /news/threads/{thread_id}` | limit | - | **nobody** |
| `GET /news/threads/{thread_id}/timeline` | - | - | **nobody** |
| `GET /news/ticker/{symbol}` | as_of, days, from, limit, to | - | agent |
| `GET /news/watchlist/news` | days, limit | - | **nobody** |
| `POST /news/watchlist/sync` | - | - | **nobody** |
| `GET /news/watchlist/tickers` | - | - | **nobody** |
| `POST /news/watchlist/tickers` | - | tickers* | **nobody** |
| `DELETE /news/watchlist/tickers/{symbol}` | - | - | **nobody** |
| `GET /v1/stage1/vinu-news/fetch/{ticker}/{granularity}/{time_range}/{method}` | limit | - | **nobody** |
| `POST /v1/stage1/vinu-news/trigger/{ticker}/{granularity}/{time_range}` | - | - | **nobody** |

## portfolio

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /portfolio/allocation-history` | limit | - | **nobody** |
| `GET /portfolio/daily-allocation` | - | - | live |
| `GET /portfolio/daily-game-plan` | - | - | **nobody** |
| `POST /portfolio/evaluate-batch` | - | candidates*, daily_allocation | agent |
| `GET /portfolio/health` | - | - | **nobody** |
| `GET /portfolio/not-funded` | - | - | **nobody** |
| `GET /portfolio/risk/status` | - | - | agent |
| `GET /portfolio/state` | - | - | agent; live |
| `GET /portfolio/strategies` | - | - | agent |
| `GET /portfolio/weights` | - | - | **nobody** |

## reflection

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /reflection/beliefs/notable` | limit | - | **nobody** |
| `GET /reflection/synthesis/latest` | - | - | agent |
| `GET /reflection/synthesis/pending` | as_of | - | **nobody** |

## research

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /research/angle-calibration/{angle_name}` | - | - | **nobody** |
| `GET /research/artifacts` | status, type_ | - | agent; live; portfolio |
| `GET /research/artifacts/{artifact_id}/paper-return` | lookback_days | - | live |
| `POST /research/artifacts/{artifact_id}/promote` | force | - | live |
| `GET /research/candidate-graveyard/{symbol}` | limit | - | **nobody** |
| `POST /research/decay/{artifact_id}/approve` | approver | - | **nobody** |
| `POST /research/ensure` | - | user_idea, strategy_code, symbol*, from_date*, to_date*, indicators, initial_capital, dry_run, universe | **nobody** |
| `GET /research/evaluation-history/{artifact_id}` | - | - | **nobody** |
| `GET /research/evaluation-status/by-ticker/{ticker}` | - | - | **nobody** |
| `GET /research/evaluation-status/{artifact_id}` | - | - | **nobody** |
| `GET /research/generation-rounds` | limit, symbol | - | **nobody** |
| `GET /research/generation-rounds/{generation_id}` | - | - | **nobody** |
| `GET /research/health` | - | - | **nobody** |
| `GET /research/hypotheses` | status, symbol | - | agent; live |
| `POST /research/hypotheses` | - | title*, thesis*, universe, strategy_type | agent |
| `POST /research/hypotheses/human` | - | title*, thesis*, universe, strategy_type | agent |
| `GET /research/hypotheses/{hypothesis_id}` | - | - | **nobody** |
| `POST /research/hypotheses/{hypothesis_id}/evidence` | - | run_id, iteration, metric*, value*, conclusion*, reasoning, metrics_snapshot, source, ref_id | agent; live |
| `GET /research/indicators/pool` | - | - | simulator |
| `GET /research/maturity/status` | - | - | live |
| `GET /research/move-evidence` | limit, symbol | - | **nobody** |
| `POST /research/move-evidence/{symbol}` | - | bar_ts*, window_seconds*, granularity*, atr*, price_move*, move_threshold*, direction* | live |
| `GET /research/parity-report` | min_days, min_trades | - | **nobody** |
| `GET /research/pipeline-edges` | only_problems | - | **nobody** |
| `POST /research/run` | - | user_idea, strategy_code, symbol*, from_date*, to_date*, indicators, initial_capital, dry_run, universe | agent |
| `GET /research/runs` | limit, status, symbol | - | agent |
| `DELETE /research/runs/{run_id}` | - | - | **nobody** |
| `GET /research/runs/{run_id}` | - | - | **nobody** |
| `POST /research/runs/{run_id}/approve` | - | - | **nobody** |
| `GET /research/runs/{run_id}/checkpoints` | latest_only | - | agent |
| `GET /research/settings` | - | - | **nobody** |
| `GET /research/signal-evidence` | limit, symbol | - | agent |
| `POST /research/signal-evidence/trigger` | - | trigger_id*, symbol*, trigger_time*, must_condition*, indicators, granularity, policy_version | live |
| `GET /research/signal-evidence/{trigger_id}` | - | - | agent |
| `POST /research/signal-evidence/{trigger_id}/outcome` | - | max_favorable_excursion*, max_adverse_excursion*, return_at_horizon* | **nobody** |
| `POST /research/sweep/candidate` | - | symbol*, from_date*, to_date*, recipe, params, base_code, param_name, param_value, indicators, initial_capital | agent |
| `GET /research/sweep/grid` | limit, symbol | - | **nobody** |
| `POST /research/sweep/grid` | - | symbol*, from_date*, to_date*, param_grid*, recipe, base_code, param_name, indicators, initial_capital | agent |
| `GET /research/sweep/grid/{sweep_id}` | - | - | **nobody** |
| `GET /research/sweep/recipes` | - | - | agent |
| `GET /research/symbols/{symbol}/state` | - | - | agent |
| `GET /research/track2-aggregate/{symbol}` | as_of, min_sample_size, must_condition* | - | **nobody** |
| `GET /research/trade-plan/{artifact_id}` | - | - | live; portfolio |
| `POST /research/trade-plan/{artifact_id}/action` | - | action* | live |
| `POST /research/trade-plan/{artifact_id}/approve` | approver, force | - | agent; live |
| `GET /research/trade-plan/{artifact_id}/calibration` | - | - | agent; live; portfolio |
| `POST /research/trade-plan/{artifact_id}/record-outcome` | - | actual_return_pct* | live |
| `POST /research/trade-plan/{symbol}` | - | timeframe, summary_context | agent |
| `POST /research/trade-score-calibration/approve` | approver | - | **nobody** |
| `GET /research/unconfirmed-moves` | limit, symbol | - | **nobody** |

## screener

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /health` | - | - | infra; research; simulator; strategy |
| `GET /screener/pairlist/{rule_id}` | - | - | **nobody** |
| `GET /screener/rankers` | - | - | **nobody** |
| `DELETE /screener/rankers/{ranker_id}` | - | - | **nobody** |
| `GET /screener/rankers/{ranker_id}` | - | - | **nobody** |
| `PUT /screener/rankers/{ranker_id}` | - | universe*, factors*, top_n, hard_filter, interval_sec, active | **nobody** |
| `GET /screener/rankers/{ranker_id}/churn` | limit, symbol | - | **nobody** |
| `POST /screener/rankers/{ranker_id}/disable` | - | - | **nobody** |
| `POST /screener/rankers/{ranker_id}/enable` | - | - | **nobody** |
| `GET /screener/rankers/{ranker_id}/latest` | - | - | agent; research |
| `POST /screener/rankers/{ranker_id}/rank` | - | - | **nobody** |
| `GET /screener/rules` | - | - | **nobody** |
| `DELETE /screener/rules/{rule_id}` | - | - | **nobody** |
| `GET /screener/rules/{rule_id}` | - | - | **nobody** |
| `PUT /screener/rules/{rule_id}` | - | condition*, universe*, cooldown_min, coarse_filter, actions, mode, interval_sec, active | **nobody** |
| `POST /screener/rules/{rule_id}/disable` | - | - | **nobody** |
| `POST /screener/rules/{rule_id}/dry-run` | - | - | **nobody** |
| `POST /screener/rules/{rule_id}/enable` | - | - | **nobody** |
| `GET /screener/rules/{rule_id}/history` | limit | - | **nobody** |

## simulator

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /simulator/health` | - | - | **nobody** |
| `GET /simulator/results/{run_id}` | - | - | agent |
| `GET /simulator/results/{run_id}/equity` | - | - | portfolio; research |
| `GET /simulator/results/{run_id}/metrics` | - | - | **nobody** |
| `GET /simulator/results/{run_id}/trades` | - | - | **nobody** |
| `GET /simulator/results/{run_id}/weights` | - | - | research |
| `DELETE /simulator/runs` | strategy | - | **nobody** |
| `GET /simulator/runs` | strategy, symbol | - | agent |
| `DELETE /simulator/runs/{run_id}` | - | - | **nobody** |
| `GET /simulator/settings` | - | - | **nobody** |
| `POST /simulator/simulate` | - | strategy_name*, start_date, end_date, initial_capital, transaction_cost_pct, slippage_pct, slippage_model, benchmark_tickers, allow_short, deviation_threshold, dry_run, run_validation, full_metrics, position_sizing_model, target_annual_vol, vol_lookback_days, kelly_fraction, kelly_lookback_days, max_leverage, max_pct_of_volume, execution_reject_prob, random_seed | **nobody** |
| `POST /simulator/simulate/custom` | - | strategy_code*, class_name*, symbols*, start_date, end_date, initial_capital, transaction_cost_pct, slippage_pct, slippage_model, benchmark_tickers, allow_short, deviation_threshold, interval, indicators, run_validation, full_metrics, position_sizing_model, target_annual_vol, vol_lookback_days, kelly_fraction, kelly_lookback_days, max_leverage, max_pct_of_volume, execution_reject_prob, random_seed | agent; research |

## stock-price

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /stock/backfill/runs` | limit | - | **nobody** |
| `GET /stock/backfill/status/{job_id}` | - | - | **nobody** |
| `POST /stock/backfill/trigger` | - | symbols, force | **nobody** |
| `POST /stock/candles/batch` | - | symbols*, interval, from, to, days, provider, limit, indicators, adjusted | screener |
| `GET /stock/candles/{symbol}` | adjusted, as_of, closed_only, days, from, indicators, interval, limit, provider, to | - | agent; live; portfolio; research; screener; simulator; tools |
| `GET /stock/catalog` | - | - | **nobody** |
| `GET /stock/catalog/fallbacks` | limit, symbol | - | **nobody** |
| `GET /stock/catalog/{symbol}` | - | - | **nobody** |
| `GET /stock/events/{symbol}` | within_hours | - | live |
| `GET /stock/health` | - | - | tools |
| `POST /stock/ingest/trigger` | - | - | **nobody** |
| `GET /stock/quote/{symbol}` | - | - | live |
| `GET /stock/settings` | - | - | **nobody** |
| `PATCH /stock/settings` | - | poll_interval_sec, default_provider, data_root | **nobody** |
| `POST /stock/watchlist/sync` | - | - | **nobody** |
| `GET /stock/watchlist/tickers` | - | - | initial-analysis |
| `POST /stock/watchlist/tickers` | - | tickers* | agent |
| `DELETE /stock/watchlist/tickers/{symbol}` | - | - | **nobody** |
| `GET /v1/stage1/vinu-stock-price/fetch/{ticker}/{granularity}/{time_range}` | page | - | **nobody** |
| `GET /v1/stage1/vinu-stock-price/fetch/{ticker}/{granularity}/{time_range}/{run_id}` | - | - | agent |
| `POST /v1/stage1/vinu-stock-price/trigger/{ticker}/{granularity}/{time_range}` | - | - | **nobody** |

## strategy

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /strategy/docs/yaml-reference` | - | - | **nobody** |
| `GET /strategy/health` | - | - | **nobody** |
| `DELETE /strategy/runs` | strategy | - | **nobody** |
| `GET /strategy/runs` | strategy | - | simulator |
| `DELETE /strategy/runs/{run_id}` | - | - | **nobody** |
| `GET /strategy/settings` | - | - | **nobody** |
| `GET /strategy/strategies` | - | - | agent; live; portfolio; simulator |
| `GET /strategy/strategies/{name}` | - | - | live |
| `POST /strategy/strategies/{name}/evaluate` | as_of, symbols | - | agent |
| `POST /strategy/strategies/{name}/precondition-check` | - | precondition_held | live |
| `GET /strategy/weights` | from_ts, strategy, symbol, to_ts | - | simulator |
| `DELETE /strategy/weights/{strategy}` | symbol | - | **nobody** |

## tools

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /features/catalog` | - | - | agent |
| `GET /features/factors` | group | - | **nobody** |
| `GET /features/factors/search` | q* | - | **nobody** |
| `GET /features/factors/{factor_id}` | - | - | **nobody** |
| `POST /features/factors/{factor_id}/bench` | - | (open) | **nobody** |
| `GET /features/health` | - | - | **nobody** |
| `GET /features/ml/models` | - | - | **nobody** |
| `GET /features/presets` | - | - | agent |
| `GET /features/requests` | limit, status, title | - | **nobody** |
| `POST /features/requests` | - | title*, symbols*, from_ts, to_ts, days, interval, preset, features, conditions, ml_model, ml_label, run_immediately | agent |
| `GET /features/requests/by-title/{title}` | - | - | agent |
| `DELETE /features/requests/{request_id}` | - | - | **nobody** |
| `GET /features/requests/{request_id}` | - | - | **nobody** |
| `GET /features/requests/{request_id}/data` | - | - | **nobody** |
| `POST /features/requests/{request_id}/run` | - | - | **nobody** |
| `GET /features/{symbol_or_kind}` | as_of, indicators | - | research |

