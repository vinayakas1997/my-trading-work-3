# stage2-readiness-verification — Test Log

**Status:** Weekend portion VERIFIED (2026-08-02) — broker order path fixed
(was 500), `vinu-live` durable book proven to survive a real `restart
live-api`. Real-fill confirmation deferred to the next market open
(2026-08-03), see "Deferred" below.

## What will be tested / Expected output

**This is a live smoke test, not a build task** — the two things
previously thought to be blockers (broker credential wiring, position
persistence) were already checked and found to be working; see
`e2e-test-0731/scope-responsibilities/vinu-agent.md` and `vinu-live.md`
correction notes.

Sequence:
1. Place a small paper order (1 share, liquid symbol, market hours) via
   `POST /agent/broker/order`.
2. Confirm the position in both Alpaca's own account state
   (`GET /agent/broker/positions`) and `vinu-live`'s local book
   (`BookBackend`/`list_open_positions`) — these are two different
   systems and must agree.
3. `docker compose restart live-api` (restart, not rebuild).
4. Re-check both position sources — must be unchanged.
5. Close the test position cleanly.

Pass condition: position survives the restart in both systems,
unchanged. Fail condition: either system loses or diverges on the
position — this would be the highest-priority bug found in this whole
plan, since nothing else matters if positions don't survive a restart.

Full detail: [../../scope-responsibilities/03-stage2-readiness-verification.md](../../scope-responsibilities/03-stage2-readiness-verification.md)

## Verification results (2026-08-02, weekend — market closed)

### Broker order path (`POST /agent/broker/order`)
- Market clock confirmed closed: `{'is_open': False, 'next_open':
  2026-08-03T09:30:00-04:00}` — no real fill is possible this weekend.
- Broker is configured and linked to the live $100k paper account
  (`GET /agent/broker/account` → `configured: true, equity 100000.0`).
- Submitted `{"symbol":"AAPL","side":"buy","qty":1,
  "order_type":"market","time_in_force":"day"}`.
- **Before fix:** returned HTTP 500 (see Bug-1). **After fix:** clean,
  correct guard rejection `{"status":"rejected","reason":"AAPL has no
  ACTIVE strategy artifact — ... Set require_active_artifact: false in the
  mandate to override."}`. No order was placed (guard correctly blocked; no
  market = nothing to fill). This is the documented queue/reject behavior,
  not an error — the default mandate requires an ACTIVE research artifact +
  confirmation + open market, all correct safety behavior for Stage 2.
- Verified `GET /agent/broker/positions` returns the (empty) real Alpaca
  state — endpoint itself works.

### vinu-live durable book restart-survival (the actual proof)
- Opened a test position directly in `vinu-live`'s SQLite book
  (`/data/trade_plan_book.db`, `BookBackend`) — `pos_bcc32223d29f` AAPL
  1.0 @ 220.0 (artifact_id `smoke-test-restart`). This exercises the same
  durable host bind-mount (`data/live:/data`) and schema Stage 2 uses.
- `docker compose restart live-api` (restart, not rebuild — the realistic
  Stage-2 failure mode).
- After restart, `list_open_positions` → **1 position, unchanged**
  (pos_bcc32223d29f AAPL 1.0 @ 220.0, long). **Survived.**
- Closed it cleanly afterward (`close_position`, market 220.5) → open
  positions back to 0. No dangling smoke test left behind.

**Conclusion:** the infra-level restart-survival path is proven. On a real
fill the *position must also appear in Alpaca's own account* — that half
can only be tested during market hours (deferred, below).

### Deferred — real-fill test (market hours only)
- Complete at the next market open (2026-08-03 09:30 ET): place the paper
  order when the market is actually open, confirm the position appears in
  **both** `/agent/broker/positions` (Alpaca) and `vinu-live`'s BookBackend
  and reconciles, then close it. Weekend test already confirmed the
  durable-book restart and broker-order path; the open-market fill is the
  only remaining piece.

## Bug / Fix Log

### Bug-1 — order audit write hits read-only `/var/log` → all orders 500
- **Found during:** first `POST /agent/broker/order` on the weekend queue
  test — returned `Internal Server Error`.
- **Date:** 2026-08-02
- **Symptom:** any order (rejected or executed) returned HTTP 500 with no
  usable body.
- **Reproduction:** `POST /agent/broker/order` with the minimal AAPL buy
  payload above.
- **Severity:** blocker for Stage 2 (it masks every real order).

### Fixed-1
- **Root cause:** `vinu_agent/broker/kill_switch.py::AuditLogger` wrote to a
  hardcoded `Path("/var/log/vinu/trade_audit.log")`. Container rootfs is
  read-only (only `/data` is bind-mounted rw), so `LOG_PATH.parent.mkdir` /
  open raised `OSError: [Errno 30] Read-only file system: '/var/log/vinu'`.
  TradeTool calls `AuditLogger.log` on both the rejected path and the
  execute path, so the guard's clean `{"status":"rejected"...}` string was
  never returned — the exception propagated instead.
- **Fix applied:** `AuditLogger.LOG_PATH` now reads
  `VINU_AGENT_AUDIT_LOG` or falls back to `$VINU_AGENT_DATA_ROOT` (both
  `/data` in the Docker stack) instead of `/var/log/vinu`.
- **Verification:** rebuilt `agent-api`; re-posted the order → clean
  `{"status":"rejected", ...}` response, no 500, no traceback.
- **Status:** fixed. This was a real Stage 2 blocker that would have
  failed every real paper order.