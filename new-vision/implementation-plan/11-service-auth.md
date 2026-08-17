---
name: service-auth
closes: "production-grade" gap raised in conversation (2026-08-17) — no authentication found on any internal HTTP route
status: complete (wiring) — see [11-service-auth-status.md](11-service-auth-status.md) (2026-08-17); key provisioning deferred to task 13
priority: cross-cutting foundation, sequence alongside/before tasks 01 and 04
---

# Task: add authentication to internal service routes

## Goal

Add access control (API key, bearer token, or equivalent) to every HTTP route across `vinu-agent`,
`vinu-live`, and `vinu-portfolio` — currently none of them have any.

## Why

Grepped `vinu-agent/vinu_agent/server`, `vinu-live/vinu_live/server`, `vinu-portfolio/vinu_portfolio/
server` for `middleware`, `APIKeyHeader`, `HTTPBearer`, `OAuth` — zero hits anywhere. Every route discussed
across this entire implementation plan is currently open to anyone who can reach the port: `/broker/
performance/{artifact_id}`, `/portfolio/evaluate-batch`, `/live/trade-plan/rebalance-request`, and by
extension whatever routes eventually front the Kill Switch and `mark_active`. This is very likely the
single biggest reason a review of this system as "production grade" comes back negative — it's not a
subtle gap, it's the complete absence of a layer that any system moving toward real capital needs before
anything else on this list.

There IS existing security work in this codebase — `vinu-infra/security/scanner.py` (prompt-injection
detection) and `vinu-infra/security/network.py` (SSRF guard, rejects localhost/private-IP targets), both
real and tested (`vinu-infra/tests/test_security.py`). That's *agent-input* security. This task is the
missing *service-to-service* security layer — a different concern, not yet started.

## Current state (verified 2026-08-17)

- No auth middleware, API key check, or bearer-token verification found anywhere in the three server
  packages checked.
- `vinu-infra` already exists as the shared package other services import from (used for the LLM client,
  the security scanner, SSRF guard) — the natural home for a shared auth-check utility, following the
  existing pattern rather than reimplementing per service.
- Not yet determined (check before building): whether these services are only ever reachable on a private
  network/localhost today (which would lower urgency but not eliminate it — internal-only is not the same
  as authenticated, and the plan already calls for cross-process routes like task 04's rebalance-request
  that assume services talk to each other over a real network boundary).

## Steps

1. Confirm the actual network exposure of each service today (bound to `0.0.0.0` vs `127.0.0.1`, any
   existing reverse proxy/firewall in front) — this affects urgency but not whether the work is needed.
2. Design a shared auth mechanism in `vinu-infra` — a simple shared-secret API key header
   (`X-Internal-Api-Key` or similar) checked via FastAPI dependency injection is proportionate for
   service-to-service calls between trusted internal components; this doesn't need to be full OAuth/JWT
   unless there's a reason external, untrusted clients will ever call these routes directly.
3. Add the dependency/middleware to every route in `vinu-agent`, `vinu-live`, `vinu-portfolio`'s server
   packages — including the ones added by tasks 01 and 04 in this plan, so sequence this before or
   alongside those.
4. Store the shared key via whatever secrets mechanism task 13 (secrets management) establishes — don't
   hardcode it or add it as a second, inconsistent `.env` pattern.
5. Make the failure mode explicit and loud: an unauthenticated request should get a clear 401/403, logged
   (via task 10's logging substrate) as a real security-relevant event, not silently dropped.
6. Specifically double check the Kill Switch and `mark_active`-adjacent routes get this protection —
   those are the highest-consequence endpoints in the whole system.

## Acceptance criteria

- Every route in all three server packages requires a valid credential; a request without one gets a
  clear 401/403, not a silent pass-through.
- A test suite confirms at least one route per service rejects an unauthenticated call and accepts an
  authenticated one.
- The new routes added by tasks 01 and 04 are built with this from the start, not retrofitted afterward.
- Unauthenticated attempts are logged as security-relevant events (depends on task 10 landing first, or
  at minimum basic logging existing before this ships).

## Dependencies

Should land alongside or just after task 10 (structured logging), since auth failures need to be
recorded somewhere. Sequence before or alongside tasks 01 and 04 so new routes/workers don't need
retrofitting.
