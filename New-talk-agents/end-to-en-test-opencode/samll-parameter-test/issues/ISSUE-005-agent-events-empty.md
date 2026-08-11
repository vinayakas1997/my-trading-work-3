# ISSUE-005 — Agent session events endpoint returns empty

- **Component:** vinu-agent `server/routes_sessions.py` `GET /sessions/{session_id}/events`
- **Phase found:** 2 (Block 5)
- **Severity:** LOW

## Description
`GET /agent/sessions/{session_id}/events` returned an empty body (0 bytes) for an active session that had exchanged a user message and an assistant reply. Expected a list of events (tool calls, skill usage, attempts). Health/status/session/messages endpoints all work.

## Steps to reproduce
1. `POST /agent/sessions` → `POST /sessions/{id}/messages` → `GET /sessions/{id}/events`.

## Actual
Empty body (HTTP 200, 0 bytes) — `curl` raw len 0.

## Expected
A JSON list of session events (at minimum the message/attempt events).

## Impact
Low — observability/tool-use visibility for agent sessions is missing; the message round-trip itself works.

## Suggested fix
Check whether the events store is populated when a message is sent (`SendMessageResponse.attempt_id` exists, `SessionResponse.last_attempt_id` stays null); either populate events or return `[]` explicitly with JSON content-type.

## Status
OPEN

## Evidence
- Session `686b070db934` (e2e smoke): `GET /events` → 0 bytes; `GET /messages` → 1 user + 1 assistant message.
