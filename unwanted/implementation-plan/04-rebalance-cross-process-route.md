---
name: rebalance-cross-process-route
closes: shortcoming #3 in ../01-vinu-components-shortcomings.md
status: complete — see 04-rebalance-cross-process-route-status.md
---

# Task: add a durable cross-process route for rebalance requests

## Goal

Give `capital_allocator`'s rebalancer (in `vinu-agent`) a real, durable HTTP path into `vinu-live`'s
`TradePlanOrchestrator`, so an unwind request survives being a cross-service call, not just an in-process
one.

## Why

The rebalancer must never close a position itself — it can only **request** an unwind, and
`TradePlanOrchestrator` (as sole authority over live-position close/hold) decides whether to act on that
request. This split is already correctly designed and partially built, but the actual wire between the
two services is incomplete.

## Current state (verified 2026-08-17 — re-check before building)

- `vinu-agent/vinu_agent/agent/capital_allocator_hook.py` — has a `_request_unwind` function
  (~line 104-113) that calls `check_rebalance_allowed` (from `rebalance_guard.py`) and then POSTs to
  vinu-live's `/live/trade-plan/rebalance-request`. **This already exists and works for the
  in-process/synchronous case** — better than the Phase 3 plan doc (`New-talk-agents/new-restructure/
  phases/phase-3-kill-switch/`) claims, which says `rebalance_guard` has "no real caller yet." That claim
  is stale/wrong; the real gap is narrower than it sounds.
- `vinu-live/vinu_live/trade_plan/orchestrator.py` — `submit_rebalance_request` (~line 87) and
  `_evaluate_rebalance_request` (~line 343) are real and handle the request once it arrives in-process
  within vinu-live.
- The actual gap, per Phase 5's own self-reported follow-up (confirmed still true by direct code read):
  **no durable HTTP route exists for this to arrive reliably across processes** — i.e. if `vinu-agent`
  and `vinu-live` are separate running services (which the architecture implies, given they're separate
  packages with their own `server/app.py`), the request needs a real, idempotent, retryable HTTP
  endpoint on the `vinu-live` side that `capital_allocator_hook.py`'s POST actually lands on reliably —
  not just a call that works when tested in the same process/test harness.

## Steps

1. Read `vinu-live/vinu_live/server/app.py` in full to determine whether `/live/trade-plan/
   rebalance-request` already exists as a registered route, or whether `capital_allocator_hook.py` is
   currently POSTing to a URL with no matching route (confirm which case this actually is — the earlier
   audit was not fully certain).
2. If the route doesn't exist: add it, following the same pattern as other routes in that file
   (`routes_broker.py`, `routes_ticker_ledger.py`, etc. in the sibling `vinu-agent` package are good
   reference examples for the request/response shape and error handling this codebase already uses).
3. Wire the route to call `orchestrator.submit_rebalance_request(...)`.
4. Make the request idempotent — if `capital_allocator_hook.py` retries a POST (network blip, timeout),
   the orchestrator should not double-count or double-submit the same unwind request. Use whatever
   request-ID/artifact-ID pairing already exists in the payload to dedupe.
5. Confirm the Kill Switch is still checked on this path — the design explicitly requires Kill Switch to
   block "the rebalancer's request path by default, not just `mark_active`." Verify
   `capital_allocator_hook.py`'s existing kill-switch check (confirmed present, wraps the funding
   decision) also covers this unwind-request call, not just the funding call.

## Acceptance criteria

- A rebalance-unwind request sent from `vinu-agent`'s `capital_allocator_hook.py` reliably reaches
  `vinu-live`'s `TradePlanOrchestrator.submit_rebalance_request` via a real HTTP route, verified with an
  integration test that starts both services (or realistic mocks of both) rather than calling the
  Python function directly in-process.
- A duplicate/retried request does not double-submit.
- With the Kill Switch engaged, the request path is blocked — confirmed by a test, not just code
  inspection.

## Dependencies

None, but touches both `vinu-agent` and `vinu-live` — coordinate if these are owned/worked on by
different people or agents in parallel.
