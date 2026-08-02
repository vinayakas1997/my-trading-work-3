# stage2-readiness-verification — Test Log

**Status:** Not started.

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

## Bug / Fix Log

_Nothing logged yet — testing has not started._
