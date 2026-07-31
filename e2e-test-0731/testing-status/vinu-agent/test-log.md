# vinu-agent — Test Log

**Status:** Mostly out of scope for Stage 1 (broker layer deferred to Stage 2)

## What will be tested

- Consistency check only: does `vinu-portfolio`'s real Stage 1
  `daily-game-plan` output match what the `agent-self`,
  `daily-allocation`, and `live-safety` skill docs
  (`vinu-agent/skills/`) describe the agent as expecting to read.
- Not tested in Stage 1: chat sessions, swarm runs, and the
  `AlpacaBroker` execution layer (`routes_broker.py`) — all deferred to
  Stage 2 per the earlier scope decision.

## Expected output

- The skill docs' description of the game-plan/readiness-score format
  matches the real field names and structure `vinu-portfolio` actually
  returns for a Stage 1 run — if the docs and the real output have
  drifted, that's a doc bug to log here, not a `vinu-agent` code bug.

## Bug / Fix Log

### Bug-1 — container crash-loops on startup, session store path unwritable

- **Found during:** first `docker compose up -d --build` of the full stack.
- **Date:** 2026-07-31
- **Symptom:** `agent-api` crash-loops. Logs show
  `FileNotFoundError: [Errno 2] No such file or directory: '/nonexistent/.vinu'`
  then `OSError: [Errno 30] Read-only file system: '/nonexistent'` in
  `SessionStore.__init__`.
- **Reproduction:** `docker compose up -d` then `docker compose logs agent-api`.
- **Suspected cause:** unlike every other service, `vinu-agent`'s
  Dockerfile sets **no** `VINU_AGENT_DATA_ROOT` default, and
  `vinu-components/.env` never set one either (no `.env.example` exists
  for this service, so it was missed when the shared `.env` was built).
  The code default is `~/.vinu`, which for the container's system `app`
  user (created via `adduser --system`, no home directory) resolves to
  `/nonexistent/.vinu` — completely unwritable regardless of the
  read-only-filesystem/permission fixes applied to the other services.
- **Severity:** blocker.

### Fixed-1

- **Root cause:** confirmed via `docker compose logs agent-api` —
  `VINU_AGENT_DATA_ROOT` was never set anywhere (no Dockerfile default,
  no `.env` entry), so it fell back to the code default `~/.vinu`, which
  resolves to `/nonexistent/.vinu` for the container's homeless system
  user.
- **Fix applied:** added `VINU_AGENT_DATA_ROOT=/data` to
  `vinu-components/.env`; host-directory ownership fixed via the shared
  `chown -R 100:101` fix (see
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Fixed-1).
- **Verification:** `docker compose ps` → `agent-api ... (healthy)`, no
  tracebacks in `docker compose logs agent-api`.
- **Status:** fixed.
