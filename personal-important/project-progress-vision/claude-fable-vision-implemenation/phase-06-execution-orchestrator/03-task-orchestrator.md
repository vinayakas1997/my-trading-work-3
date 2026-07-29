# Task 3: Trade-Plan Orchestrator

**Status:** DONE

## Purpose

The Phase 6 loop itself: fetch `ACTIVE` `type=trade_plan` artifacts, enter positions for
newly-approved plans, evaluate contingency/invalidation rules for open ones, gate every order
on Phase 5's breaker, and reconcile Phase 3's book against the broker's actual positions.

## Approach

- `TradePlanOrchestrator.cycle()`: lists active artifacts via the existing
  `GET /research/artifacts?status=ACTIVE&type_=trade_plan` (no new vinu-research endpoint
  needed — that summary omits `trade_plan_data`, so each artifact's full plan is then fetched
  via Phase 4's `GET /research/trade-plan/{artifact_id}`), fetches live prices and portfolio
  value once per cycle, then per-plan either enters (`_maybe_enter`) or evaluates
  (`_evaluate_open_position`), and finishes with `_reconcile_book_with_broker`.
- `_maybe_enter`: skips `neutral`-direction or zero-size plans; on a `long`/`short` plan with no
  existing position, checks the breaker, submits a market order via `agent-api`'s existing
  `/broker/order` (already `OrderGuard`-protected — kill switch, mandate, market hours), and
  only writes to Phase 3's book (`open_position`) when the order response is `submitted`.
- `_evaluate_open_position`: computes live metrics, checks invalidation rules first (exit takes
  priority over an in-trade adjustment), then contingency rules (`reduce_position` submits a
  breaker-gated partial-close order; `tighten_stop` is bookkeeping-only, no broker order —
  updates `Position.stop_loss` via the new `update_stop_loss`). An unrecognized contingency
  `action` string is explicitly logged and left unhandled, never guessed at.
- `_check_breaker`: called from all three order-attempting paths (entry, invalidation exit,
  contingency reduce) before `_submit_order` — no code path reaches the broker without it.
  Computes a live covariance matrix via Phase 1's `dynamic_covariance` when 2+ symbols are
  held; `cluster_map=None` otherwise (documented scope boundary, see `00-implementation.md`
  design decision #4).
- `_reconcile_book_with_broker`: reuses the pre-existing `ReconciliationEngine`
  (`reconciliation.py`) every cycle, diffing the book's open positions against
  `GET /broker/positions` and logging any drift — broker is ground truth.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/trade_plan/orchestrator.py` | — | Created |
| `vinu_live/book/positions.py` | — | Added `daily_realized_pnl`, `update_stop_loss` |
| `vinu_live/book/__init__.py` | — | Exported the two additions |

## Verification

- [x] Tests pass (`tests/test_trade_plan_orchestrator.py`, 17 tests — including 3 full-`cycle()` integration tests exercising entry, existing-position evaluation, and the no-active-plans skip path together, not just individual methods in isolation)
- [x] Type checks pass
- [x] Manual verification done
- [x] No runtime LLM call introduced outside `vinu-research`
