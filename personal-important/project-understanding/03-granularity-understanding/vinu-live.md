# vinu-live

## What it is

The automated execution layer: turns an ACTIVE trade plan artifact into
real broker orders, manages the open-position lifecycle every cycle
(invalidation, trailing stop, bracket-partial, correlation trim), and
feeds realized outcomes back to `vinu-research`. Everything in this doc
below the pipeline section is verified precisely by this session's own
`scenarios-test/01-07` work, not paraphrased from memory.

## Trigger / cadence

Four independent worker loops (`cli.py`, each its own process, each its
own real default interval — `config.py`):

| Worker | Default interval | What it does |
|---|---|---|
| `trade-plan-worker` | 300s (5 min) | Drives `TradePlanOrchestrator.cycle()` — the real order-execution loop. |
| `trade-plan-approval-worker` | 300s | G2a's auto-approve worker (`CalibrationGate`-based, bootstraps off the origin strategy's own promotion bar on first approval). |
| `feedback-worker` | 300s | `FeedbackLoopWorker.cycle()` — closed-position feedback to `vinu-research`. |
| `shadow-worker` | 3600s (1h) | `ShadowEvaluator.evaluate_all()` — BENCHING→ACTIVE promotion checks against paper-trading track record. |

## Pipeline

**`cycle()`** (`trade_plan/orchestrator.py`, every 5 min), real order,
confirmed via `scenarios-test`:
1. `_fetch_active_trade_plans()` — `GET /research/artifacts?status=ACTIVE&type_=trade_plan`,
   then `GET /research/trade-plan/{artifact_id}` per result for the full
   plan blob.
2. `_fetch_prices(symbols)` — spot price per symbol,
   `GET /stock/candles/{symbol}?interval=1d&days=5`.
3. `_fetch_portfolio_value()` — real broker equity
   (`GET /agent/broker/account`), falls back to a large configured
   default when unconfigured (a real, documented risk if an operator
   forgets to configure the broker — sizes against a phantom balance).
4. `_check_broker_health()` — one `/agent/broker/account` probe;
   `self._broker_degraded` set only after `BROKER_STALE_SEC` (default
   180s) of continued failure past the last confirmed-healthy probe (a
   single blip inside the grace window doesn't pause anything).
5. `_is_trading_halted()` — refreshes the local mirror of the agent's
   real kill switch (`GET /agent/broker/status`) for this cycle.
6. Shock-batch prioritization — plans sorted by
   `shock_clustering`/`shock_personality` score (from
   `vinu-initial-analysis`) descending, so the highest-risk open position
   is evaluated first when any symbol scores above 0.5.
7. Per plan/symbol: no open position → `_maybe_enter()`; open position →
   `_evaluate_open_position()` (see below).
8. `_reconcile_book_with_broker(prices)` — pulls the book toward the real
   broker holding on drift. A confirmed-flat account (a real 200 with an
   empty list) now correctly auto-closes a stale position (scenario 06's
   fix); a genuine fetch failure still skips, fail-open.
9. `_check_runtime_correlation(prices)` — real DCC/shrinkage covariance
   from actual price history (not mocked, per scenario 05); a
   dangerously co-moving pair's larger-market-value side gets
   `reduce_only`-trimmed.
10. `_check_ood(prices)` — out-of-distribution detector (crisis
    correlation, vol explosion, single-day gap signals); dormant unless
    `VINU_LIVE_OOD_DETECTOR` is `alert`/`halt`/`flatten`.

**`_maybe_enter()`** — the entry gate chain, in order (each a real,
independently-observable `entry_blocked_by_*` action): emergency halt →
broker-outage pause (`_broker_degraded`) → signal conflict → stale
signal → data-freshness → CVaR tail gate → event blackout → liquidity/
spread gate → borrow check (shorts) → cooldown → turbulence. Passing all
of them: `qty = size_pct * portfolio_value / price` (vol-target-scaled),
a real order submitted with a `stop_loss_price` attached
(`price*(1-cvar_95_limit)`) — the one-time, static catastrophic backstop,
a REAL resting broker order, never re-placed.

**`_evaluate_open_position()`** — the exit/adjustment gate chain, in
order (confirmed this session, scenario by scenario):
1. Contingency rules (tighten stop / reduce position).
2. Invalidation conditions — a real breach submits a `reduce_only` close
   via `_broker_close_plan()` (never over-asks the broker, never sells
   into a flat account — `_apply_invalidation`).
3. Pending rebalance request (advisory, evaluated *after*, never
   preempting, invalidation/contingency).
4. Trailing-stop ratchet — **bookkeeping only**, confirmed by reading the
   code: nothing compares live price to the ratcheted `stop_loss` to
   trigger an exit. It only feeds the next step's risk distance.
5. Bracket partial at 1R+ — take-fraction scales with the R-multiple
   actually achieved (25% at 1R, 50% at 2R, capped 75%, fixed this
   session's reasoning audit from a flat 50%).
6. Otherwise `hold`.

None of the above is gated by `_broker_degraded` or the local halted
mirror except entries — confirmed both structurally and against a real
outage (scenario 04: the exit is still *attempted* during an outage,
reports `exit_not_filled` truthfully rather than a false success, and
retries every cycle until the broker actually answers).

**Feedback cycle** (every 5 min, `FeedbackLoopWorker.cycle()`): every
closed-but-unprocessed book position →
`_record_calibration_outcome` (writes back to `vinu-research`'s
`judgment_store`) + `_push_pnl_attribution` + `_refresh_personality_stats`
(triggers a targeted `shock_personality`/`shock_clustering` re-run for
just that symbol in `vinu-initial-analysis`, not the full 28-angle suite)
+ `_record_hypothesis_evidence` + `_write_ticker_ledger_closeout`.
`mark_feedback_processed` happens **before** the evidence writes
(persist-before-evidence ordering, so a failure in the writes never
re-opens or reprocesses the same close).

## Storage

- `book/positions.py` — the local SQLite position ledger (`Position`,
  `Fill`), the thing every guard above reconciles against the broker.
- `RebalanceRequestQueue` — pending advisory rebalance asks.

## Talks to

- **Outbound**: `vinu-research` (plans, approval, calibration/evidence
  writes), `vinu-stock-price` (price + returns), `vinu-initial-analysis`
  (shock scores), `/agent/broker/*` on `vinu-agent` (every real order,
  account/positions/status reads, the same `TradeTool`/`OrderGuard` path
  interactive orders use).
- **Inbound**: none — nothing calls into `vinu-live`'s own HTTP surface
  as part of the trading hot path; its API exists for manual/inspection
  use (`run-cycle`, `run-trade-plan-cycle` one-shot triggers).
