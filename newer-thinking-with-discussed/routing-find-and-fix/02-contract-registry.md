# Contract registry (GENERATED — do not edit by hand)

Produced by `python -m vinu_infra.contract_scan`. Producers = the real OpenAPI of every service app; consumers = every
HTTP call found in the source. Re-run it after any route or caller change; `contracts.json` next to this file is the
machine-readable copy.

- Services read: 13 of 13
- Routes: 272; HTTP calls found in source: 206; calls matched to a route: 200
- Findings: 1 ERROR, 0 WARN (see `03-findings.md` for what each means and its fix status)
- Routes nothing in the code calls: 165 (candidate-gap: 10, covered: 2, file-read: 3, human-view: 85, operator-action: 65); each is classified in the last column.

Legend: `*` = required. Body `(open)` = untyped object, any key accepted. Callers are `file:line`.

## agent

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /agent/admin/settings` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `PATCH /agent/admin/settings` | - | (open) | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /agent/admin/settings/schema` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `POST /agent/admin/settings/{name}/reset` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /agent/broker/account` | - | - | live; portfolio |
| `GET /agent/broker/asset/{symbol}` | - | - | live |
| `POST /agent/broker/halt` | - | scope, reason | live; portfolio |
| `GET /agent/broker/limits` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `DELETE /agent/broker/limits/{symbol}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /agent/broker/limits/{symbol}` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `PUT /agent/broker/limits/{symbol}` | - | max_order_value, max_position_pct, max_capital_utilization_pct, reason, set_by | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /agent/broker/limits/{symbol}/history` | limit | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `GET /agent/broker/mandate` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `POST /agent/broker/mandate/renew` | - | days, until | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /agent/broker/order` | - | symbol*, side*, qty*, order_type, limit_price, stop_price, time_in_force, take_profit_price, stop_loss_price, stop_loss_limit_price, reduce_only, client_order_id | live |
| `GET /agent/broker/order/{order_id}` | - | - | live |
| `GET /agent/broker/overrides` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `DELETE /agent/broker/overrides/{symbol}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `PUT /agent/broker/overrides/{symbol}` | - | state*, reason, set_by | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /agent/broker/performance/{artifact_id}` | - | - | live; research |
| `POST /agent/broker/performance/{artifact_id}` | - | daily_returns* | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /agent/broker/performance/{artifact_id}/append` | - | daily_return*, trade_date* | live |
| `GET /agent/broker/positions` | - | - | live; portfolio; screener |
| `POST /agent/broker/resume` | - | scope | live |
| `GET /agent/broker/safety-ledger` | limit | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `GET /agent/broker/status` | scope | - | live |
| `GET /agent/health` | - | - |  |
| `POST /agent/live-decision/run` | - | ticker*, strategy_id*, trigger_id, mode, position_context, novelty | live |
| `POST /agent/notify/reconciliation-drift` | - | symbol*, action*, book_qty, broker_qty, expected_qty, actual_qty, drift_pct, detail | live |
| `POST /agent/notify/symbol-conflict` | - | symbol*, contributions*, net_weight*, gross_weight*, severity* | portfolio |
| `POST /agent/notify/trade-plan-pending` | - | artifact_id*, symbol*, reasons | live |
| `GET /agent/options/{symbol}/snapshot` | expiration, limit | - | research |
| `GET /agent/sessions` | limit | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `POST /agent/sessions` | - | title, as_of | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `DELETE /agent/sessions/{session_id}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /agent/sessions/{session_id}` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `POST /agent/sessions/{session_id}/cancel` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /agent/sessions/{session_id}/events` | last_event_id | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `GET /agent/sessions/{session_id}/messages` | limit | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `POST /agent/sessions/{session_id}/messages` | - | content*, as_of | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /agent/status` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `GET /agent/swarm/presets` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `POST /agent/swarm/runs` | - | preset_name*, user_vars* | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /agent/swarm/runs/ensure-fresh` | max_age_minutes, preset_name*, symbol* | - | live |
| `GET /agent/swarm/runs/latest` | preset_name*, symbol* | - | research |
| `GET /agent/swarm/runs/{run_id}` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |
| `POST /agent/swarm/runs/{run_id}/cancel` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /agent/ticker-ledger/event` | - | ticker*, stage*, event_type*, text, ref_id, source | live |
| `GET /agent/trace/{ref_id}` | - | - | **nobody** — human-view: agent sessions, swarm runs, broker limits and overrides, safety ledger, settings: read by a person or the UI |

## initial-analysis

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /analysis/angle/{angle_name}/{ticker}` | granularity | - | agent; live; research; strategy |
| `GET /analysis/angles` | active | - | agent |
| `GET /analysis/correlation/batch` | from_ts, symbols*, to_ts | - | strategy |
| `GET /analysis/correlation/{ticker}` | from_ts, to_ts | - | agent; research |
| `GET /analysis/coverage/{ticker}` | - | - | **nobody** — human-view: coverage and manifest views for an operator (the agent computes coverage itself from /angles) |
| `GET /analysis/drawdown/{ticker}` | from_ts, to_ts | - | research; strategy |
| `GET /analysis/events/{ticker}` | from_ts, to_ts | - | **nobody** — candidate-gap: older analysis views; research and strategy read story / drawdown / correlation / angle instead, check whether these are still needed |
| `GET /analysis/health` | - | - |  |
| `GET /analysis/impact/{ticker}` | from_ts, to_ts | - | strategy |
| `GET /analysis/manifest` | - | - | **nobody** — human-view: coverage and manifest views for an operator (the agent computes coverage itself from /angles) |
| `POST /analysis/pnl-attribution/{ticker}/record` | - | closed_positions* | live |
| `GET /analysis/run/jobs/{job_id}` | - | - | **nobody** — human-view: job status poll for a person who triggered a run |
| `POST /analysis/run/{ticker}` | angle_names, background, from_ts, to_ts | - | live; research |
| `GET /analysis/settings` | - | - | **nobody** — human-view: service settings: read by a person or the UI |
| `GET /analysis/story/{ticker}` | from_ts, to_ts | - | research |
| `GET /analysis/symbols` | - | - | agent |
| `GET /v1/stage1/vinu-initial-analysis/factsheet/{ticker}/{method}` | tier | - | **nobody** — candidate-gap: the positional stage-1 API (fetch / factsheet) exists beside the older /analysis, /stock and /news routes, but the pipeline still reads the older ones (only latest-run is used); decide which API is the canonical one |
| `GET /v1/stage1/vinu-initial-analysis/fetch/{ticker}/{granularity}/{time_range}/{method}` | - | - | **nobody** — candidate-gap: the positional stage-1 API (fetch / factsheet) exists beside the older /analysis, /stock and /news routes, but the pipeline still reads the older ones (only latest-run is used); decide which API is the canonical one |
| `GET /v1/stage1/vinu-initial-analysis/fetch/{ticker}/{granularity}/{time_range}/{method}/{run_id}` | - | - | **nobody** — candidate-gap: the positional stage-1 API (fetch / factsheet) exists beside the older /analysis, /stock and /news routes, but the pipeline still reads the older ones (only latest-run is used); decide which API is the canonical one |
| `GET /v1/stage1/vinu-initial-analysis/latest-run/{ticker}` | - | - | agent |
| `POST /v1/stage1/vinu-initial-analysis/trigger/{ticker}/{granularity}/{time_range}/{method}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |

## live

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /live/admin/settings` | - | - | **nobody** — human-view: service settings: read by a person or the UI |
| `PATCH /live/admin/settings` | - | (open) | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /live/admin/settings/schema` | - | - | **nobody** — human-view: service settings: read by a person or the UI |
| `POST /live/admin/settings/{name}/reset` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /live/cycle` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /live/decision-context/{ticker}/{strategy_id}` | - | - | agent |
| `GET /live/decisions/needs-sizing` | limit | - | **nobody** — human-view: visibility routes (order ledger, lockouts, slippage, snapshots, decisions needing a size) for an operator; reflection reads the live data files |
| `GET /live/decisions/{ticker}/{strategy_id}` | limit | - | agent |
| `GET /live/executions` | limit, symbol | - | **nobody** — human-view: visibility routes (order ledger, lockouts, slippage, snapshots, decisions needing a size) for an operator; reflection reads the live data files |
| `POST /live/feedback/cycle` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /live/health` | - | - |  |
| `GET /live/lockouts` | - | - | **nobody** — human-view: visibility routes (order ledger, lockouts, slippage, snapshots, decisions needing a size) for an operator; reflection reads the live data files |
| `POST /live/shadow-evaluate` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /live/snapshots/{symbol}` | - | - | **nobody** — human-view: visibility routes (order ledger, lockouts, slippage, snapshots, decisions needing a size) for an operator; reflection reads the live data files |
| `GET /live/snapshots/{symbol}/{angle_name}/history` | limit | - | **nobody** — human-view: visibility routes (order ledger, lockouts, slippage, snapshots, decisions needing a size) for an operator; reflection reads the live data files |
| `GET /live/status` | - | - | **nobody** — human-view: visibility routes (order ledger, lockouts, slippage, snapshots, decisions needing a size) for an operator; reflection reads the live data files |
| `GET /live/tca/slippage` | symbol | - | **nobody** — human-view: visibility routes (order ledger, lockouts, slippage, snapshots, decisions needing a size) for an operator; reflection reads the live data files |
| `POST /live/trade-plan/cycle` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /live/trade-plan/emergency-flatten` | - | reason | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /live/trade-plan/emergency-resume` | - | reason | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /live/trade-plan/emergency-status` | - | - | **nobody** — human-view: emergency flatten / halt status for an operator |
| `POST /live/trade-plan/rebalance-request` | - | symbol*, reason*, critical | agent |

## models

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `POST /models/angle/{angle}/compute` | - | symbol*, bars, news, from_ts, to_ts, time_format | infra |
| `GET /models/angles` | - | - | **nobody** — human-view: model service status and angle list for an operator |
| `POST /models/finbert/score` | - | texts*, batch_size | infra |
| `GET /models/health` | - | - |  |
| `GET /models/status` | deep | - | **nobody** — human-view: model service status and angle list for an operator |

## news

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /news/articles/since` | limit, ts* | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `GET /news/backfill/job/{job_id}` | - | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `GET /news/backfill/status` | - | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `POST /news/backfill/trigger` | ticker | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /news/backfill/{ticker}/toggle` | - | enabled* | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /news/feeds` | all | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `PATCH /news/feeds/{feed_id}` | - | enabled* | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /news/finbert/backfill` | batch_size | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /news/finbert/job/{job_id}` | - | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `GET /news/health` | - | - |  |
| `GET /news/high-impact` | hours, limit, sentiment | - | **nobody** — candidate-gap: news impact / threat classification is stored and shown but no gate or agent reads it (see 04 status, Open: News) |
| `POST /news/ingest/ticker-news` | days | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /news/ingest/trigger` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /news/latest` | date, limit, provider, tiers | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `GET /news/poll/status` | - | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `GET /news/providers` | - | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `PATCH /news/providers/{provider_id}` | - | enabled* | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /news/search` | limit, q* | - | agent |
| `GET /news/settings` | - | - | **nobody** — human-view: service settings: read by a person or the UI |
| `PATCH /news/settings` | - | mode, poll_interval_sec, active_tiers, backfill_start_date, backfill_pause_on_error | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /news/stats/ticker/{symbol}` | days | - | **nobody** — candidate-gap: news impact / threat classification is stored and shown but no gate or agent reads it (see 04 status, Open: News) |
| `GET /news/threads/active` | hours, limit | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `GET /news/threads/{thread_id}` | limit | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `GET /news/threads/{thread_id}/timeline` | - | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `GET /news/ticker/{symbol}` | as_of, days, from, limit, to | - | agent |
| `GET /news/watchlist/news` | days, limit | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `POST /news/watchlist/sync` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /news/watchlist/tickers` | - | - | **nobody** — human-view: news ingestion status, feeds, providers, threads and article lists for an operator or the UI |
| `POST /news/watchlist/tickers` | - | tickers* | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `DELETE /news/watchlist/tickers/{symbol}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /v1/stage1/vinu-news/fetch/{ticker}/{granularity}/{time_range}/{method}` | limit | - | **nobody** — candidate-gap: the positional stage-1 API (fetch / factsheet) exists beside the older /analysis, /stock and /news routes, but the pipeline still reads the older ones (only latest-run is used); decide which API is the canonical one |
| `POST /v1/stage1/vinu-news/trigger/{ticker}/{granularity}/{time_range}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |

## portfolio

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /portfolio/allocation-history` | limit | - | **nobody** — human-view: allocation history, not-funded, game plan, weights: operator views |
| `GET /portfolio/daily-allocation` | - | - | live |
| `GET /portfolio/daily-game-plan` | - | - | **nobody** — human-view: allocation history, not-funded, game plan, weights: operator views |
| `POST /portfolio/evaluate-batch` | - | candidates*, daily_allocation | agent |
| `GET /portfolio/health` | - | - |  |
| `GET /portfolio/not-funded` | - | - | **nobody** — human-view: allocation history, not-funded, game plan, weights: operator views |
| `GET /portfolio/risk/status` | - | - | agent |
| `GET /portfolio/state` | - | - | agent; live |
| `GET /portfolio/strategies` | - | - | agent |
| `GET /portfolio/weights` | - | - | **nobody** — human-view: allocation history, not-funded, game plan, weights: operator views |

## reflection

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /reflection/beliefs/notable` | limit | - | agent |
| `GET /reflection/synthesis/latest` | - | - | agent |
| `GET /reflection/synthesis/pending` | as_of | - | **nobody** — human-view: pending synthesis list for an operator; the worker reads its own store |

## research

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /research/angle-calibration/{angle_name}` | - | - | **nobody** — candidate-gap: calibration and graveyard are written and used in-process; nothing reads these views, check whether an agent should |
| `GET /research/artifacts` | status, type_ | - | agent; live; portfolio |
| `GET /research/artifacts/{artifact_id}/paper-return` | lookback_days | - | live |
| `POST /research/artifacts/{artifact_id}/promote` | force | - | live |
| `GET /research/candidate-graveyard/{symbol}` | limit | - | **nobody** — candidate-gap: calibration and graveyard are written and used in-process; nothing reads these views, check whether an agent should |
| `POST /research/decay/{artifact_id}/approve` | approver | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /research/ensure` | - | user_idea, strategy_code, symbol*, from_date*, to_date*, indicators, initial_capital, dry_run, universe | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /research/evaluation-history/{artifact_id}` | - | - | **nobody** — file-read: the agent and reflection read the same strategy-evaluation database directly (edge evaluation_status->agent.idea_prompt), not over HTTP |
| `GET /research/evaluation-status/by-ticker/{ticker}` | - | - | **nobody** — file-read: the agent and reflection read the same strategy-evaluation database directly (edge evaluation_status->agent.idea_prompt), not over HTTP |
| `GET /research/evaluation-status/{artifact_id}` | - | - | **nobody** — file-read: the agent and reflection read the same strategy-evaluation database directly (edge evaluation_status->agent.idea_prompt), not over HTTP |
| `GET /research/generation-rounds` | limit, symbol | - | **nobody** — human-view: introspection and report routes for an operator (pipeline-edge report, parity report, generation rounds, sweeps, hypotheses) |
| `GET /research/generation-rounds/{generation_id}` | - | - | **nobody** — human-view: introspection and report routes for an operator (pipeline-edge report, parity report, generation rounds, sweeps, hypotheses) |
| `GET /research/health` | - | - |  |
| `GET /research/hypotheses` | status, symbol | - | agent; live |
| `POST /research/hypotheses` | - | title*, thesis*, universe, strategy_type | agent |
| `POST /research/hypotheses/human` | - | title*, thesis*, universe, strategy_type | agent |
| `GET /research/hypotheses/{hypothesis_id}` | - | - | **nobody** — human-view: introspection and report routes for an operator (pipeline-edge report, parity report, generation rounds, sweeps, hypotheses) |
| `POST /research/hypotheses/{hypothesis_id}/evidence` | - | run_id, iteration, metric*, value*, conclusion*, reasoning, metrics_snapshot, source, ref_id | agent; live |
| `GET /research/indicators/pool` | - | - | simulator |
| `GET /research/maturity/status` | - | - | agent; live |
| `GET /research/move-evidence` | limit, symbol | - | **nobody** — covered: the live-decision agent gets Track-2 moves through `unconfirmed_moves[]` in get_live_decision_context (see its AGENT.md); no dedicated tool by decision |
| `POST /research/move-evidence/{symbol}` | - | bar_ts*, window_seconds*, granularity*, atr*, price_move*, move_threshold*, direction* | live |
| `GET /research/parity-report` | min_days, min_trades | - | **nobody** — human-view: introspection and report routes for an operator (pipeline-edge report, parity report, generation rounds, sweeps, hypotheses) |
| `GET /research/pipeline-edges` | only_problems | - | **nobody** — human-view: introspection and report routes for an operator (pipeline-edge report, parity report, generation rounds, sweeps, hypotheses) |
| `POST /research/run` | - | user_idea, strategy_code, symbol*, from_date*, to_date*, indicators, initial_capital, dry_run, universe | agent |
| `GET /research/runs` | limit, status, symbol | - | agent |
| `DELETE /research/runs/{run_id}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /research/runs/{run_id}` | - | - | **nobody** — human-view: introspection and report routes for an operator (pipeline-edge report, parity report, generation rounds, sweeps, hypotheses) |
| `POST /research/runs/{run_id}/approve` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /research/runs/{run_id}/checkpoints` | latest_only | - | agent |
| `GET /research/settings` | - | - | **nobody** — human-view: service settings: read by a person or the UI |
| `GET /research/signal-evidence` | limit, symbol | - | agent; live |
| `POST /research/signal-evidence/trigger` | - | trigger_id*, symbol*, trigger_time*, must_condition*, indicators, granularity, policy_version | initial-analysis; live |
| `GET /research/signal-evidence/{trigger_id}` | - | - | agent |
| `POST /research/signal-evidence/{trigger_id}/outcome` | - | max_favorable_excursion*, max_adverse_excursion*, return_at_horizon* | initial-analysis; live |
| `POST /research/sweep/candidate` | - | symbol*, from_date*, to_date*, recipe, params, base_code, param_name, param_value, indicators, initial_capital | agent |
| `GET /research/sweep/grid` | limit, symbol | - | **nobody** — human-view: introspection and report routes for an operator (pipeline-edge report, parity report, generation rounds, sweeps, hypotheses) |
| `POST /research/sweep/grid` | - | symbol*, from_date*, to_date*, param_grid*, recipe, base_code, param_name, indicators, initial_capital | agent |
| `GET /research/sweep/grid/{sweep_id}` | - | - | **nobody** — human-view: introspection and report routes for an operator (pipeline-edge report, parity report, generation rounds, sweeps, hypotheses) |
| `GET /research/sweep/recipes` | - | - | agent |
| `GET /research/symbols/{symbol}/state` | - | - | agent |
| `GET /research/track2-aggregate/{symbol}` | as_of, min_sample_size, must_condition* | - | **nobody** — covered: the live-decision agent gets Track-2 moves through `unconfirmed_moves[]` in get_live_decision_context (see its AGENT.md); no dedicated tool by decision |
| `GET /research/trade-plan/{artifact_id}` | - | - | live; portfolio |
| `POST /research/trade-plan/{artifact_id}/action` | - | action* | live |
| `POST /research/trade-plan/{artifact_id}/approve` | approver, force | - | agent; live |
| `GET /research/trade-plan/{artifact_id}/calibration` | - | - | agent; live; portfolio |
| `POST /research/trade-plan/{artifact_id}/record-outcome` | - | actual_return_pct* | live |
| `POST /research/trade-plan/{symbol}` | - | timeframe, summary_context | agent |
| `POST /research/trade-score-calibration/approve` | approver | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /research/unconfirmed-moves` | limit, symbol | - | agent |

## screener

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /health` | - | - | infra; research; simulator; strategy |
| `GET /screener/pairlist/{rule_id}` | - | - | **nobody** — human-view: rules, rankers, pairlist, churn, history: operator views (the agent reads rankers through /latest) |
| `GET /screener/rankers` | - | - | **nobody** — human-view: rules, rankers, pairlist, churn, history: operator views (the agent reads rankers through /latest) |
| `DELETE /screener/rankers/{ranker_id}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /screener/rankers/{ranker_id}` | - | - | **nobody** — human-view: rules, rankers, pairlist, churn, history: operator views (the agent reads rankers through /latest) |
| `PUT /screener/rankers/{ranker_id}` | - | universe*, factors*, top_n, hard_filter, interval_sec, active | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /screener/rankers/{ranker_id}/churn` | limit, symbol | - | **nobody** — human-view: rules, rankers, pairlist, churn, history: operator views (the agent reads rankers through /latest) |
| `POST /screener/rankers/{ranker_id}/disable` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /screener/rankers/{ranker_id}/enable` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /screener/rankers/{ranker_id}/latest` | - | - | agent; research |
| `POST /screener/rankers/{ranker_id}/rank` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /screener/rules` | - | - | **nobody** — human-view: rules, rankers, pairlist, churn, history: operator views (the agent reads rankers through /latest) |
| `DELETE /screener/rules/{rule_id}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /screener/rules/{rule_id}` | - | - | **nobody** — human-view: rules, rankers, pairlist, churn, history: operator views (the agent reads rankers through /latest) |
| `PUT /screener/rules/{rule_id}` | - | condition*, universe*, cooldown_min, coarse_filter, actions, mode, interval_sec, active | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /screener/rules/{rule_id}/disable` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /screener/rules/{rule_id}/dry-run` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /screener/rules/{rule_id}/enable` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /screener/rules/{rule_id}/history` | limit | - | **nobody** — human-view: rules, rankers, pairlist, churn, history: operator views (the agent reads rankers through /latest) |

## simulator

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /simulator/health` | - | - |  |
| `GET /simulator/results/{run_id}` | - | - | agent |
| `GET /simulator/results/{run_id}/equity` | - | - | portfolio; research |
| `GET /simulator/results/{run_id}/metrics` | - | - | **nobody** — human-view: backtest result detail for an operator (the agent reads equity and weights) |
| `GET /simulator/results/{run_id}/trades` | - | - | **nobody** — human-view: backtest result detail for an operator (the agent reads equity and weights) |
| `GET /simulator/results/{run_id}/weights` | - | - | research |
| `DELETE /simulator/runs` | strategy | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /simulator/runs` | strategy, symbol | - | agent |
| `DELETE /simulator/runs/{run_id}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /simulator/settings` | - | - | **nobody** — human-view: service settings: read by a person or the UI |
| `POST /simulator/simulate` | - | strategy_name*, start_date, end_date, initial_capital, transaction_cost_pct, slippage_pct, slippage_model, benchmark_tickers, allow_short, deviation_threshold, dry_run, run_validation, full_metrics, position_sizing_model, target_annual_vol, vol_lookback_days, kelly_fraction, kelly_lookback_days, max_leverage, max_pct_of_volume, execution_reject_prob, random_seed | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /simulator/simulate/custom` | - | strategy_code*, class_name*, symbols*, start_date, end_date, initial_capital, transaction_cost_pct, slippage_pct, slippage_model, benchmark_tickers, allow_short, deviation_threshold, interval, indicators, run_validation, full_metrics, position_sizing_model, target_annual_vol, vol_lookback_days, kelly_fraction, kelly_lookback_days, max_leverage, max_pct_of_volume, execution_reject_prob, random_seed | agent; research |

## stock-price

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /stock/backfill/runs` | limit | - | **nobody** — human-view: data catalog and backfill status for an operator |
| `GET /stock/backfill/status/{job_id}` | - | - | **nobody** — human-view: data catalog and backfill status for an operator |
| `POST /stock/backfill/trigger` | - | symbols, force | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /stock/candles/batch` | - | symbols*, interval, from, to, days, provider, limit, indicators, adjusted | screener |
| `GET /stock/candles/{symbol}` | adjusted, as_of, closed_only, days, from, indicators, interval, limit, provider, to | - | agent; initial-analysis; live; news; portfolio; research; screener; simulator; tools |
| `GET /stock/catalog` | - | - | **nobody** — human-view: data catalog and backfill status for an operator |
| `GET /stock/catalog/fallbacks` | limit, symbol | - | **nobody** — human-view: data catalog and backfill status for an operator |
| `GET /stock/catalog/{symbol}` | - | - | **nobody** — human-view: data catalog and backfill status for an operator |
| `GET /stock/events/{symbol}` | within_hours | - | live |
| `GET /stock/health` | - | - | tools |
| `POST /stock/ingest/trigger` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /stock/quote/{symbol}` | - | - | live |
| `GET /stock/settings` | - | - | **nobody** — human-view: service settings: read by a person or the UI |
| `PATCH /stock/settings` | - | poll_interval_sec, default_provider, data_root | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `POST /stock/watchlist/sync` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /stock/watchlist/tickers` | - | - | initial-analysis |
| `POST /stock/watchlist/tickers` | - | tickers* | agent |
| `DELETE /stock/watchlist/tickers/{symbol}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /v1/stage1/vinu-stock-price/fetch/{ticker}/{granularity}/{time_range}` | page | - | **nobody** — candidate-gap: the positional stage-1 API (fetch / factsheet) exists beside the older /analysis, /stock and /news routes, but the pipeline still reads the older ones (only latest-run is used); decide which API is the canonical one |
| `GET /v1/stage1/vinu-stock-price/fetch/{ticker}/{granularity}/{time_range}/{run_id}` | - | - | agent |
| `POST /v1/stage1/vinu-stock-price/trigger/{ticker}/{granularity}/{time_range}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |

## strategy

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /strategy/docs/yaml-reference` | - | - | **nobody** — human-view: strategy YAML reference and settings for a person |
| `GET /strategy/health` | - | - |  |
| `DELETE /strategy/runs` | strategy | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /strategy/runs` | strategy | - | simulator |
| `DELETE /strategy/runs/{run_id}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /strategy/settings` | - | - | **nobody** — human-view: service settings: read by a person or the UI |
| `GET /strategy/strategies` | - | - | agent; live; portfolio; simulator |
| `GET /strategy/strategies/{name}` | - | - | agent; live |
| `POST /strategy/strategies/{name}/evaluate` | as_of, symbols | - | agent |
| `POST /strategy/strategies/{name}/precondition-check` | - | precondition_held | live |
| `GET /strategy/weights` | from_ts, strategy, symbol, to_ts | - | simulator |
| `DELETE /strategy/weights/{strategy}` | symbol | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |

## tools

| Route | Query | JSON body | Called by |
|---|---|---|---|
| `GET /features/catalog` | - | - | agent |
| `GET /features/factors` | group | - | **nobody** — human-view: factor and model catalog, feature requests: operator and UI views |
| `GET /features/factors/search` | q* | - | **nobody** — human-view: factor and model catalog, feature requests: operator and UI views |
| `GET /features/factors/{factor_id}` | - | - | **nobody** — human-view: factor and model catalog, feature requests: operator and UI views |
| `POST /features/factors/{factor_id}/bench` | - | (open) | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /features/health` | - | - |  |
| `GET /features/ml/models` | - | - | **nobody** — human-view: factor and model catalog, feature requests: operator and UI views |
| `GET /features/presets` | - | - | agent |
| `GET /features/requests` | limit, status, title | - | **nobody** — human-view: factor and model catalog, feature requests: operator and UI views |
| `POST /features/requests` | - | title*, symbols*, from_ts, to_ts, days, interval, preset, features, conditions, ml_model, ml_label, run_immediately | agent |
| `GET /features/requests/by-title/{title}` | - | - | agent |
| `DELETE /features/requests/{request_id}` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /features/requests/{request_id}` | - | - | **nobody** — human-view: factor and model catalog, feature requests: operator and UI views |
| `GET /features/requests/{request_id}/data` | - | - | **nobody** — human-view: factor and model catalog, feature requests: operator and UI views |
| `POST /features/requests/{request_id}/run` | - | - | **nobody** — operator-action: state-changing route; called by an operator, the UI or a scheduler outside the code scanned, never by another service |
| `GET /features/{symbol_or_kind}` | as_of, indicators | - | research; strategy |

