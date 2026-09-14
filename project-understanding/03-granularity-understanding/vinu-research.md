# vinu-research

## What it is

The synthesis/authoring layer: turns raw angle data (from
`vinu-initial-analysis`) and news into an actual trade plan artifact via
one LLM call, manages that artifact's lifecycle (CREATED → BENCHING →
ACTIVE, decay, revalidation), and owns the promotion gate that decides
whether a strategy is trusted with real capital. **This is where "move to
summary" actually happens** — but read the honest finding below about
exactly how much of the 28-angle suite that summary step currently uses.

## Trigger / cadence

No single loop — several independent scheduled processes plus an HTTP
API, all separate CLI subcommands (`cli.py`):

- `vinu-research serve` — HTTP API, always up.
- `vinu-research schedule-decay --interval-hours=N` — decay-scan on a
  repeating interval (checks ACTIVE/MONITORING artifacts for performance
  decay).
- `vinu-research schedule-freshness` — two independent interval timers in
  one process: `revalidation_scan()` and `regime_recompute_scan()`
  (`ScheduledResearchExecutor`) — deliberately calls these two directly
  rather than running the executor's own internal loop, because that loop
  also runs a second, separately-implemented decay policy that would run
  concurrently with (and diverge from) `schedule-decay`'s — noted in the
  code as an unreconciled duplication, not fixed yet.
- `vinu-research run` — the strategy research loop (hypothesis-driven
  backtest sweep — this is closer to research/backtesting workflow than
  the live trade-plan path below).
- Trade plan **authoring itself is on-demand, not scheduled** — triggered
  by an HTTP call (see Pipeline).

## Pipeline

**Trade plan authoring** (`POST /research/trade-plan/{symbol}`,
`server/routes_trade_plan.py::generate_trade_plan` →
`trade_plan_authoring.py::author_trade_plan`) — the actual "then move to
summary" step:
1. **Fetch risk state** (`fetch_risk_state`) — *not* read from
   `vinu-initial-analysis`'s GARCH angle. Pulls raw daily-return candles
   directly from `vinu-stock-price` (`ResearchTools.get_benchmark_data`)
   and computes its own GARCH volatility path, VaR/CVaR (95%), expected
   1-day move, win rate, Kelly fraction — independently, in-process.
2. **Fetch personality features** (`fetch_personality_features`) — this
   IS reading from `vinu-initial-analysis`, but only **2 of the 28
   angles**: `tools.get_angle_rows("shock_personality", symbol)` and
   `tools.get_angle_rows("shock_clustering", symbol)` (each just the
   latest row). **Honest finding, worth stating plainly for future
   checkpoint testing**: the other 26 angles (arima, chronos, lstm,
   kalman_filters, dlinear, moirai, patchtst, tft, regime_analysis,
   trend_lifecycle, news_price_causality, peer_relative_strength, etc.)
   are computed and stored by `vinu-initial-analysis` every hour, but are
   **not currently read by trade-plan authoring at all**. They exist,
   they're queryable (`GET /analysis/angle/{name}/{ticker}`), but this
   specific synthesis step doesn't consume them yet.
3. **Generate forecast** (`forecast_skill.py::generate_forecast`) — the
   actual LLM call. Builds a flat text prompt from the risk-state dict +
   the 2-angle personality dict (`_build_forecast_prompt`), calls
   `ResearchLlmClient.chat_json(system_prompt, user_prompt)`
   (`llm.py`) with a fixed system prompt, parses back
   `direction`/`confidence`/`magnitude_pct`/`magnitude_std`/`horizon_days`/`reasoning`.
   Fails soft: an unparseable/failed LLM response becomes a neutral
   `direction="neutral", confidence=0.0` forecast, not an exception.
4. **Build risk bands / contingency rules / invalidation conditions**
   (`_build_risk_band`/`_build_contingency_rules`/`_build_invalidation_conditions`)
   — deterministic Python, not LLM — turns the risk state + forecast into
   the concrete numeric fields `vinu-live`'s orchestrator actually
   consumes (`max_position_size_pct`, `cvar_95_limit`,
   `invalidation_conditions` as metric/operator/threshold triples, not
   free text — so Phase 6/`vinu-live` can evaluate them mechanically).
5. `freeze_trade_plan(store, plan)` — writes the artifact, status
   `CREATED` (not yet tradeable — approval is a separate step).

**Approval** (`POST /research/trade-plan/{artifact_id}/approve`,
`trade_plan_authoring.py::approve_trade_plan`) — moves `CREATED` →
`BENCHING` (paper) or, per the bootstrap-deadlock fix found while
building Stage 0's G2a, `ACTIVE` directly on an origin strategy's first
approval. Supports `force`/`approver` for a logged manual override of a
gate rejection.

**Promotion gate** (`POST /research/artifacts/{id}/promote`,
`promotion.py::meets_promotion_bar`) — BENCHING → ACTIVE, the actual
"trusted with capital" bar. Checks the artifact's paper-trading track
record against configured thresholds (deflated Sharpe / PSR, drawdown,
minimum paper days — `vinu-live`'s `shadow_evaluator.py` supplies the
paper metrics this reads) plus an optional `CorrelationVerdict` (don't
promote a strategy too correlated with what's already ACTIVE — `gates/correlation_gate.py`).

**Decay scan** (`_run_decay_scan`, on the `schedule-decay` interval) —
re-checks ACTIVE/MONITORING artifacts against `DecayThresholds`;
crossing a threshold triggers `_trigger_re_research(symbol)` — a fresh
`author_trade_plan` run for that symbol, same pipeline as above.

**Freshness scans** (`schedule-freshness`'s two timers) —
`revalidation_scan()` and `regime_recompute_scan()`
(`scheduled/executor.py::ScheduledResearchExecutor`) keep an artifact's
supporting data current between full re-research cycles.

## Storage

- `storage/strategy_store.py` (`SqliteStrategyStore`) — every artifact
  (hypothesis, trade plan, sweep result), its status, its full
  `trade_plan_data` JSON blob. This is what `vinu-live`'s
  `_fetch_active_trade_plans()` polls (`GET /research/artifacts?status=ACTIVE&type_=trade_plan`
  then `GET /research/trade-plan/{artifact_id}` for the full blob).
- `hypothesis_registry.py` — human- or LLM-submitted trading ideas that
  feed the `autopilot`/`run` research-loop workflow (a more manual,
  backtest-scaffold-generating path, distinct from the on-demand
  trade-plan-authoring path above).
- `judgment_store.py` — calibration tracking, `record_realized_outcome`'s
  target (what a plan actually predicted vs. what happened).

## Talks to

- **Outbound**: `vinu-stock-price` (raw candles for its own risk-state
  computation), `vinu-initial-analysis` (`shock_personality`/`shock_clustering`
  angle rows only, per the finding above), an LLM provider
  (`ResearchLlmClient`).
- **Inbound**: `vinu-live`'s orchestrator polls `GET /research/artifacts`
  + `GET /research/trade-plan/{id}` every cycle to know what to trade;
  `vinu-agent`'s Telegram approve-plan flow calls
  `POST /trade-plan/{id}/approve`; `vinu-live`'s `shadow_evaluator.py`
  feeds paper-performance numbers back into the promotion gate's
  decision.
