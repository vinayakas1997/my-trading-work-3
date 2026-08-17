# Block 5 — Agent / Live

Cross-service smoke: agent session + live shadow evaluation.

Run date: 2026-08-11. Both services needed `docker compose up -d agent-api live-api`
(they were DOWN per plan Phase 0 — this was already done earlier in the session).

## Agent
- Endpoint: `POST /agent/...` (session / chat)
- Expected: agent responds, LLM reachable, broker paper configured

| Check | Expected | Actual | Status |
|---|---|---|---|
| `/agent/health` | ok, LLM reachable | ok, uptime 24372s, 31 skills, llm gemma-4-31b-it:free | PASS |
| Broker paper configured | configured: true | configured: true, equity 100,000 / cash 100,000 | PASS |
| Agent session response | valid reply | session 686b070db934 created (0.70s); message accepted (1.13s); assistant reply surfaced LLM 429 (daily free-tier quota exhausted) as graceful error message | PASS WITH DEVIATION |

## Live shadow evaluation
- Endpoint: `POST /live/...` (shadow evaluation)
- Expected: evaluation executes against paper broker / real endpoint

| Check | Expected | Actual | Status |
|---|---|---|---|
| `/live/status` | idle | idle | PASS |
| Shadow evaluation runs | success | ok, n_artifacts 0 (no approved artifacts yet — AAPL research stopped at validation) | PASS |
| Order path exercised (require_confirmation: false) | order placed / skipped in paper | not exercised — no approved artifact to shadow | NOT EXERCISED |

## Evidence
- `evidence/05-agent-live/` (curl/response transcripts captured during run)

## Deviations / Issues
- Agent assistant reply: OpenRouter free-tier 429 (`free-models-per-day-high-balance`, X-RateLimit-Remaining: 0). Graceful degradation, but no substantive reply possible until daily reset. See `../issues/`.
- `GET /agent/sessions/{id}/events` returns empty (0 bytes) for an active session — possibly a gap. See `../issues/`.
- Shadow-evaluate returned 0 artifacts because no ACTIVE research artifact exists; requires an approved artifact to exercise the order path.
