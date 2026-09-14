# vinu-agent

## What it is

The LLM-agent layer: turns raw research (angles, hypotheses) into
artifacts moving through the BENCHING → PEND → ACTIVE lifecycle, is the
one place any real broker order actually gets submitted (via
`OrderGuard`), and hosts the Telegram/Discord interface. This doc covers
the **operational/execution side verified in depth this session**
(worker cadences, the order-safety chain) — for the LLM team roster's own
internal per-agent behavior (Summary Agent, Planner, Researcher/Executor,
risk_gatekeeper, capital_allocator, Monitor), see
`project-understanding/04-new-full-explanation-v2.md`'s "Per-agent
detail" section, which stays the source of truth for that layer; this doc
adds the real cadences and the concrete safety-chain steps that doc
doesn't cover.

## Trigger / cadence

Five independent scheduled worker loops (`cli.py`, each its own `*_worker_main`,
each its own process), plus the always-up HTTP API + Telegram/Discord
bot. Real default intervals (`config.py`, all env-overridable):

| Worker | Default interval | What it does |
|---|---|---|
| `skill-audit-worker` | 3600s (1h) | Audits agent skill files for drift. |
| `planner-worker` | 1800s (30 min) | Refreshes stale Summary Agent reads, runs Planner triage, hands off to the research team. |
| `significance-worker` | 900s (15 min) | `significance_triage.py` — statistical-significance gating before something reaches the planner. |
| `risk-gatekeeper-worker` | 900s (15 min) | Reviews every BENCHING/MONITORING artifact for portfolio fit. |
| `capital-allocator-worker` | 900s (15 min) | Funds every PEND (risk-gatekeeper-approved) artifact against the configured risk budget. |

## Pipeline

**Planner worker** (every 30 min, `cli.py::planner_worker_main`):
1. `bootstrap_new_tickers(service, config.watchlist_seed_tickers)` — cold-starts
   a screener run for any configured seed ticker not yet in
   `TickerSummaryStore` (the watchlist bootstrap step).
2. Watchlist = `service.ticker_summary_store.list_summaries()` — i.e. the
   watchlist here is **derived from which tickers already have a Summary
   Agent read on file**, not an independent config list.
3. Per ticker (bounded-parallel pool, `max_workers=config.summary_parallelism`,
   serial when only one is stale — the common case):
   - `RunLogTrigger.refresh_if_stale(ticker, summary_agent_fn)` — checks
     whether `vinu-initial-analysis` has a new `run_id` since the last
     Summary Agent pass for this ticker; only calls the LLM
     (`make_summary_agent_fn`) if so.
   - `ChangeGate` — even after a refresh, decides whether anything
     actually *changed* enough to matter since the last Planner pass.
   - Only a real "yes" from `ChangeGate` reaches `PlannerTriage` →
     `make_planner_on_yes` → the actual research-team hand-off (the
     `Researcher/Executor` team from `04-new-full-explanation-v2.md`).

**Risk-gatekeeper worker** (every 15 min, `run_risk_gatekeeper_cycle`):
1. Lists every artifact in `BENCHING` or `MONITORING` status.
2. Per artifact (sequential if only one, bounded-parallel `max_workers=2`
   for a batch): `run_team_for_ticker(service, "risk_gatekeeper", task, ...)`
   — the LLM team's own process (`GetPortfolioTool` → `ComputePositionSizeTool`
   → a final JSON verdict, `APPROVED`/`REJECTED`).
3. The team's own hook (`agent/risk_gatekeeper_hook.py`) applies the
   `BENCHING`/`MONITORING` → `PEND` transition — this worker never
   mutates artifact state directly, only invokes the team.

**Capital-allocator worker** (every 15 min, `run_capital_allocator_cycle`):
1. Collects every `PEND` artifact (risk-gatekeeper-approved, awaiting
   funding) in one batch.
2. Hands the whole batch + the configured risk budget to the
   `capital_allocator` team in one call (not per-artifact) — it decides
   allocation across the batch together, not independently per artifact.
3. `agent/capital_allocator_hook.py` applies `PEND` → `ACTIVE` (funded)
   or leaves it `PEND` (not funded this cycle).

**Significance worker** (every 15 min): `significance_triage.py` — a
statistical gate that runs before Planner triage even considers a
ticker, filtering out moves/signals that aren't statistically meaningful
enough to spend an LLM call on.

## The order-safety chain (verified this session, `scenarios-test/06`/`07`)

Every real order, whether from an interactive Telegram session or
`vinu-live`'s automated cycle, goes through the exact same path — `POST
/agent/broker/order` → `TradeTool.execute()` → `OrderGuard.check()` →
`AlpacaBroker.submit_order()`. `OrderGuard.check()`'s real order of
checks (`broker/order_guard.py`, confirmed by reading the code, not
assumed):
1. **Kill switch** (`is_trading_halted(scope=symbol)`) — global halt
   checked first, then symbol-scoped. A `reduce_only=True` order is
   exempted **only when** `VINU_LIVE_HALT_POLICY=entries_only` (the
   default) — verified in scenario 07 against the real filesystem switch,
   not mocked.
2. **Order-rate throttle** — 10 orders/sec/instance sliding window
   (`VINU_AGENT_ORDER_THROTTLE_PER_SEC`).
3. **Per-symbol override** (`symbol_overrides.py`) — an operator-set
   `UNTRADEABLE`/`REDUCE_ONLY`/`IGNORED` state, checked before the
   mandate.
4. **Mandate expiry** — stale consent blocks new/increasing positions,
   `reduce_only` exempt.
5. **Notional/position-size caps** against `TradingMandate` (with
   per-symbol overrides from `symbol_limits.py` able to tighten them
   further) — `max()` of `estimated_value`/`qty*price`, fail-closed for
   an unpriceable entry.
6. **Risk budget** (`_check_risk_budget`) — warning/reduce/halt tiers off
   realized P&L vs. equity; only blocks *new/increasing* exposure,
   `reduce_only` skips it (risk-reducing an already-halted symbol is
   exactly what should still work).
7. Order actually submitted to the real broker
   (`AlpacaBroker.submit_order`) — a `stop_loss_price` on the request
   attaches a real resting `order_class="oto"` stop leg at the broker
   (the catastrophic backstop `vinu-live`'s orchestrator relies on).

**Audit trail** (`broker/kill_switch.py::AuditLogger`, verified via this
session's traceability work): every step above that rejects or approves
writes a structured JSONL entry with `session_id`/`symbol`; a successful
submission additionally logs an `order_placed` entry with the real
broker order id. `GET /agent/trace/{ref_id}` aggregates this log
(substring search) with `TeamRunStore`, `strategy_store`, and
`PaperPerformanceStore` for any session/artifact/order id in one call.

## Talks to

- **Outbound**: `vinu-research` (artifact reads/writes, trade-plan
  approve), `vinu-initial-analysis` (angle reads for the Summary Agent),
  Alpaca (the real broker), Telegram/Discord APIs.
- **Inbound**: `vinu-live`'s automated orchestrator submits orders here
  (`POST /agent/broker/order`) — the one shared code path with
  interactive LLM-submitted orders, confirmed this session (not two
  separate, divergent paths as an earlier pass in this session
  incorrectly assumed before checking).
