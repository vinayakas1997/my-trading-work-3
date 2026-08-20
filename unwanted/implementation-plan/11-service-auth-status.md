---
name: 11-service-auth-status
task: 11-service-auth
status: complete (wiring) — key provisioning deferred to task 13 (secrets)
date: 2026-08-17
---

# Status: 11-service-auth

## Re-verification note (audit was substantially stale)

The task file claimed "no auth middleware, API key check, or bearer-token
verification found anywhere in the three server packages checked." Direct code
read found the opposite:

- `vinu-infra/auth.py` already ships a complete, timing-safe (`hmac.compare_digest`)
  opt-in bearer-token check, `require_auth`, with a passing test suite
  (`vinu-infra/tests/test_auth.py`).
- `vinu-infra/server.py:101-107` already auto-applies `Depends(require_auth)` to
  every router in `create_app()`. Eight services already inherit auth from it
  (verified by grep): vinu-agent, vinu-news, vinu-research, vinu-simulator,
  vinu-stock-price, vinu-strategy (+ its merged_app), vinu-initial-analysis,
  vinu-tools.
- Only two services build `FastAPI(...)` directly and bypass it:
  `vinu-portfolio/vinu_portfolio/server/app.py:28-29` and
  `vinu-live/vinu_live/server/app.py:20-21`.

So the real task was wiring the existing shared mechanism into those two, not
building an auth layer from scratch.

## Files touched

- `vinu-portfolio/vinu_portfolio/server/app.py` — imported `require_auth`; registered
  the router with `dependencies=[Depends(require_auth)]`.
- `vinu-live/vinu_live/server/app.py` — same two changes.
- `vinu-portfolio/tests/test_auth.py` — new: 4 tests.
- `vinu-live/tests/test_auth.py` — new: 4 tests.

## What I did

Attached `Depends(require_auth)` to each service's router. Because `require_auth`
no-ops when its module-level `VINU_API_KEY` is empty, the attachment is
unconditional and preserves the existing opt-in semantics exactly (routes stay
open with no key configured; every route requires `Authorization: Bearer <key>`
once a key is set). This mirrors `vinu_infra/server.py:102-107` precisely — same
shared dependency, same failure mode (401 missing/malformed, 403 wrong key).

## What is achieved

- Every HTTP route in all three plan-relevant server packages now sits behind the
  same shared auth gate when a key is configured (acceptance #1).
- A test suite per service confirms: unauthenticated → 401 (with `WWW-Authenticate:
  Bearer`), wrong token → 403, correct token → 200, and no-key → open
  (acceptance #2). 8 tests added, all green.
- Routes added by tasks 01/04 later in this plan will be born inside these same
  routers, so they inherit auth automatically.

## Alignment with plan / justification

- **Followed as written:** shared mechanism in `vinu-infra` reused rather than
  reimplemented per service; failure mode explicit (401/403, not silent pass);
  the two highest-consequence services (the ones holding `/portfolio/evaluate-batch`
  and the Kill Switch / rebalance / shadow routes) are now covered.
- **Deviations / notes:**
  1. The plan's step 4 (store the shared key via task 13's secrets mechanism) is
     deliberately not done here — task 13 is explicitly lower urgency and needs a
     deployment decision from the user. Until then the key is a plain `VINU_API_KEY`
     env var, consistent with every other credential in `.env`. Task 13 must migrate
     it when it lands.
  2. Because `VINU_API_KEY` is read at import time (existing `vinu_infra.auth`
     design), enabling auth is: set `VINU_API_KEY` in `.env` before the process
     starts. No code change needed.

## Testing

- `python3 -m pytest vinu-portfolio/tests -q` → **120 passed** (4 new auth tests).
- `python3 -m pytest vinu-live/tests -q` → **156 passed** (4 new auth tests).

## Notes for downstream tasks

- Task 04's rebalance route lives in `vinu-live/server/app.py` — it will inherit
  auth automatically. `capital_allocator_hook.py`'s HTTP POST to it (and
  `allocation_tool.py`'s POST to `/portfolio/evaluate-batch`) must send the
  `Authorization: Bearer <key>` header once a key is configured — verify this is
  part of task 04's scope.
- Task 13 must treat `VINU_API_KEY` as a real credential to migrate out of plain
  `.env`.