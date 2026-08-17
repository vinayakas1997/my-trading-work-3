---
task: 04-rebalance-cross-process-route.md
status: complete
---

# Status: task 04 — add a durable cross-process route for rebalance requests

## Files touched

- `vinu-agent/vinu_agent/agent/capital_allocator_hook.py` — added `_auth_headers()` and pass it on the
  unwind-request POST.
- `vinu-agent/tests/test_capital_allocator_hook.py` — added `TestUnwindCrossProcessWire` (4 tests):
  end-to-end over the real wire, retry idempotency through HTTP, Bearer header attached when key set,
  no header when no key.

## What I did

- Verified the route already exists: `vinu-live/vinu_live/server/app.py:70-92`
  `/live/trade-plan/rebalance-request` → `orchestrator.submit_rebalance_request(symbol, reason)`.
  Durable by construction: `RebalanceRequestQueue` is SQLite-backed at a shared on-disk path
  (`config.data_root / "rebalance_requests.db"`), so the HTTP route's throwaway orchestrator instance
  and the trade-plan-worker's long-running instance see the same rows.
- Confirmed idempotency is inherent: the queue upserts one pending request per symbol (SQLite PRIMARY
  KEY on `symbol`), so a retried POST for the same unwind overwrites the row instead of stacking a
  duplicate. Added an HTTP-level test proving two identical decisions produce exactly one row.
- Confirmed the Kill Switch already gates the request path at both levels, with tests:
  `rebalance_guard.check_rebalance_allowed` fail-closes to the real kill switch
  (`vinu-agent/tests/test_rebalance_guard.py`) and `_request_unwind` blocks before POSTing
  (`test_blocked_by_kill_switch_does_not_post` in `test_capital_allocator_hook.py`).
- **Found and fixed the one real integration gap** the audit missed: task 11 wired `require_auth` into
  vinu-live's app, but `_request_unwind`'s POST carried no credentials — once `VINU_API_KEY` is set, the
  unwind request would have 401'd in production. Added `_auth_headers()` (opt-in: only sends
  `Authorization: Bearer <key>` when `vinu_infra.auth.VINU_API_KEY` is configured; nothing when unset,
  matching the opt-in auth contract).
- Added the end-to-end test the acceptance criterion asks for: `_request_unwind`'s real `httpx.post`
  through a `MockTransport` handler that forwards into the **real** FastAPI app (real route, real
  `submit_rebalance_request`, real SQLite queue), then a separate `RebalanceRequestQueue` instance reads
  the request — both services' real code running, only the network hop shimmed.

## What is achieved

- An unwind request from vinu-agent's `capital_allocator_hook` reliably reaches vinu-live's
  `submit_rebalance_request` via a real, durable HTTP route, idempotent under retries, kill-switch-gated,
  and authenticated whenever a key is configured.

## Alignment with plan-justification

- Task steps 1-3 resolved to "route already exists, correctly wired, durable" — the audit's uncertainty
  about whether the route existed was resolved in its favor; steps 2/3 were already done.
- Step 4 (idempotency) was already satisfied by the queue's per-symbol upsert; the new test pins it
  through the HTTP path.
- Step 5 (kill switch on the request path) was already satisfied and tested; re-verified, nothing to add.

## Testing

- `python3 -m pytest vinu-agent/tests/test_capital_allocator_hook.py -q` → 18 passed.
- `python3 -m pytest vinu-agent/tests -q` → 806 passed.
- `python3 -m pytest vinu-live/tests -q` → 156 passed.
- `python3 -m py_compile` clean on the edited module.