---
name: stage2-readiness-verification
component: vinu-live, vinu-agent
status: not-started
---

# Item 3 — Stage 2 Live-Trading Readiness — Verification Only

## Important: this is NOT a build task

Two things previously documented as "blockers" in
`e2e-test-0731/scope-responsibilities/vinu-agent.md` and `vinu-live.md`
were checked directly against the running system on 2026-08-02 and found
to be **false** (both files have correction notes now — read those
first, in full, before doing anything here, so this work doesn't start
from a wrong premise):

1. `AlpacaBroker` credentials are already wired
   (`ALPACA_API_KEY`/`ALPACA_API_SECRET` in `vinu-components/.env`,
   `agent-api` already has `env_file: .env`) and already connected —
   `GET http://localhost:8086/agent/broker/account` returns a live
   $100k paper account.
2. `vinu-live`'s position tracking (`vinu_live/book/positions.py`,
   `BookBackend`) is a real SQLite store on a genuine host bind-mount
   (`./data/live:/data` in `docker-compose.yml`), not in-memory.

**Do not re-implement either of these.** The only real remaining gap is
that nobody has *observed* the restart-survival behavior live — reading
the code and the compose file is strong evidence, not proof. This item is
a smoke test, not a feature.

## What to actually do

1. Place a small paper order via the broker — `POST /agent/broker/order`,
   confirmed live at `vinu_agent/server/routes_broker.py:100-101`, body
   shape is `OrderRequest` (same file, lines 87-97): `{"symbol": "AAPL",
   "side": "buy", "qty": 1, "order_type": "market"}` is the minimal valid
   payload. Use a tiny quantity (1 share of a liquid symbol) during market
   hours — check `GET /agent/broker/account` or the broker's `get_clock()`
   first to confirm the market is actually open, since Alpaca will
   reject/queue orders outside market hours.
2. Confirm the position shows up:
   `GET /agent/broker/positions` and separately check `vinu-live`'s own
   book if `vinu-live` was the one that opened it
   (`vinu_live/book/positions.py::list_open_positions`) — these are two
   different systems (`AlpacaBroker` reads Alpaca's own account state;
   `vinu-live`'s `BookBackend` is vinu's own local ledger) and Stage 2
   needs BOTH to agree, not just one.
3. Restart the `live-api` container: `docker compose restart live-api`
   (do NOT rebuild — a restart is the realistic Stage-2 failure mode;
   Docker Desktop restarts, host reboots, unrelated crashes are all
   restarts, not rebuilds).
4. Re-check both position sources after restart. The position must still
   be there in both. If Alpaca shows it but `vinu-live`'s local book
   doesn't (or vice versa), that's a real, previously-undiscovered bug —
   log it, don't paper over it.
5. Close the test position afterward (don't leave a dangling paper
   position sitting around from a smoke test) via
   `POST /agent/broker/order` (opposite side) or the equivalent
   `vinu-live` close-position path.

## Files relevant (read, likely don't need to modify any of them — this is a live test, not a code change)

- `vinu-components/vinu-agent/vinu_agent/broker/alpaca.py` — `submit_order()`, `get_positions()`, `get_account()`, `get_clock()`.
- `vinu-components/vinu-agent/vinu_agent/server/routes_broker.py` — the actual HTTP route wiring for the above (confirm exact paths/params before calling — this plan infers `/agent/broker/order` from the `/agent` route_prefix pattern already confirmed live via `/agent/broker/account`, but the exact request body shape needs a direct read of this file).
- `vinu-components/vinu-live/vinu_live/book/positions.py` — `open_position()`, `list_open_positions()`, `close_position()`.
- `vinu-components/docker-compose.yml` lines 319-356 (`live-api` service block) — for the restart command and to re-confirm the volume mount hasn't changed since this plan was written.

## Expected output / how to verify

- A documented, timestamped record (in this folder's `testing-status/`)
  of: order placed → position confirmed in both Alpaca and vinu-live's
  book → container restarted → position re-confirmed in both, unchanged
  → position closed cleanly.
- If this passes cleanly, Stage 2 (per
  `e2e-test-0731/stage-2-plan.md`) has no remaining known blocker on the
  infrastructure side — the open questions left in that doc (rebalance
  cadence, pass/fail bar, monitoring) become the only things left to
  decide before Stage 2 actually starts.
- If it doesn't pass cleanly, this is the highest-priority bug in the
  whole plan — nothing else here matters if positions don't survive a
  restart.
