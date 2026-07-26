# Phase 6: Execution Engine + Live Orchestrator

**Status:** COMPLETED
**Started:** 2026-07-27
**Completed:** 2026-07-27
**Source doc:** ../claude-fable-vision/phase-06-execution-orchestrator.md
**Depends on:** Phase 3 (book), Phase 4 (frozen trade plan), Phase 5 (circuit breaker)
**Blocks:** Phase 7

## What It Delivers

A scheduled loop (`TradePlanOrchestrator`) that reads Phase 4's frozen `ACTIVE` trade-plan
artifacts, evaluates their pre-written contingency/invalidation conditions against live
market data, checks Phase 5's circuit breaker immediately before every single order attempt,
and places/manages orders via the existing broker integration — writing every resulting
position/fill into Phase 3's book as its sole writer. Zero LLM calls, by construction: every
action is a mechanical evaluation of a rule Phase 4 already wrote.

## Key discovery before implementation

`vinu-live` already contained a substantial, **pre-existing** execution system —
`scheduler.py` (`LiveScheduler`), `execution.py`, `signal_translator.py`,
`reconciliation.py`, `shadow_evaluator.py` — plus a real broker integration in `vinu-agent`
(`broker/alpaca.py`, `broker/order_guard.py`, `broker/kill_switch.py`, exposed at
`POST /broker/order` etc.). None of it was built by this vision plan (commit `da8e7660`,
predates Phase 1). It is a **portfolio target-weight rebalancer** reading from
`vinu-strategy`'s portfolio API — confirmed via repo-wide grep that it imports neither
`vinu_live.book` (Phase 3) nor `vinu_live.breaker` (Phase 5) anywhere. This is not what the
source doc describes.

## Open Questions Resolved

1. **Phase 6 is a new, parallel orchestrator — it does not modify or merge with
   `LiveScheduler`.** Different execution paradigms (portfolio-weight rebalancing vs.
   per-symbol frozen-trade-plan execution), different upstream producers. Reuses what's
   genuinely shared: the broker order endpoint (already `OrderGuard`-protected), price
   fetching, and `reconciliation.py`'s `ReconciliationEngine`.
2. **Entry trigger = plan approval, not a separate structured entry condition.** Phase 4's
   `TradePlan` has no structured entry-condition fields — only mechanically evaluable
   `contingency_rules`/`invalidation_conditions`. The forecast+calibration gate *is* the entry
   decision (already made upstream, per `00-vision-summary.md`). When an artifact is `ACTIVE`
   and the book has no open position for its symbol, Phase 6 enters at
   `risk_bands.max_position_size_pct` of portfolio value; thereafter only the mechanical rules
   govern action.
3. **`vinu-live` never imports `vinu_research.models`.** `trade_plan_data` arrives as a plain
   JSON dict, parsed directly — preserving the 3-environment isolation boundary (Live-Trading
   talks to Research-Simulations over HTTP only). `condition_evaluator.py` reimplements the
   same 6-operator set independently rather than importing `ContingencyRule`.
4. **Breaker checked immediately before every single order attempt** — entry, a
   contingency-triggered reduce, an invalidation exit. No code path skips it (see
   `orchestrator.py`'s `_maybe_enter`/`_apply_invalidation`/`_apply_contingency`, each calling
   `_check_breaker` before `_submit_order`). Aggregate-VaR's covariance matrix is computed live
   from Phase 1's `dynamic_covariance` over the book's current symbols; `cluster_map` is passed
   `None` (documented, not built — assembling a correlation→label reduction here would be false
   precision Phase 5's own tests didn't require beyond a synthetic map).
5. **Order state: optimistic book write + end-of-cycle reconciliation**, not a fill-polling
   state machine. `POST /broker/order` can return `pending_confirmation` (mandate requires
   human confirm) or `rejected` — Phase 6 never bypasses that; it only writes to Phase 3's book
   when the response `status == "submitted"`. Every cycle ends by reusing
   `ReconciliationEngine` to diff the book against `GET /broker/positions` (broker is ground
   truth) and logs any drift.
6. **"No rule matched" is always explicitly logged** (`"No rule triggered for {symbol} --
   holding unchanged"`), satisfying the source doc's no-improvisation test — verified by
   `test_no_rule_triggered_holds_and_logs`.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu_live/trade_plan/condition_evaluator.py` | vinu-live | create |
| `vinu_live/trade_plan/live_metrics.py` | vinu-live | create |
| `vinu_live/trade_plan/orchestrator.py` | vinu-live | create |
| `vinu_live/trade_plan/__init__.py` | vinu-live | create |
| `vinu_live/book/positions.py` | vinu-live | modify — added `daily_realized_pnl`, `update_stop_loss` |
| `vinu_live/book/__init__.py` | vinu-live | modify — export the two additions |
| `vinu_live/config.py` | vinu-live | modify — `research_api_url`, `initial_analysis_api_url`, `trade_plan_worker_interval_sec` |
| `vinu_live/cli.py` | vinu-live | modify — `trade-plan-cycle`/`trade-plan-worker` subcommands |
| `vinu_live/server/app.py` | vinu-live | modify — `POST /trade-plan/cycle` |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-condition-evaluator.md` | Mechanical rule evaluation | DONE |
| 2 | `02-task-live-metrics.md` | Live metric computation for open positions | DONE |
| 3 | `03-task-orchestrator.md` | Fetch/enter/evaluate/breaker/reconcile loop | DONE |
| 4 | `04-task-cli-server-wiring.md` | CLI subcommands + HTTP route | DONE |

## Dependencies Met

- [x] Phase 3 completed (live book ledger — `vinu_live.book`)
- [x] Phase 4 completed (frozen trade plans — `Artifact(type="trade_plan")`)
- [x] Phase 5 completed (circuit breaker — `vinu_live.breaker.check_limits`)

## Non-Negotiable Rule Check (AGENTS.md Rule 10 / Agent Rule 10)

Zero LLM calls anywhere in this phase — `condition_evaluator.py` and `live_metrics.py` are
pure functions over numbers, `orchestrator.py` only calls HTTP endpoints (vinu-research's
already-frozen artifacts, vinu-stock-price, vinu-initial-analysis's angle data, agent-api's
broker) and local book/breaker functions. No `chat_json`/LLM client is imported anywhere in
`vinu_live`. This is the direct payoff of Phase 4 being thorough: every in-trade situation this
phase can encounter is either covered by a pre-written metric/operator/threshold rule, or falls
through to the explicitly-logged "no rule triggered — hold" default, never an improvised
decision.
