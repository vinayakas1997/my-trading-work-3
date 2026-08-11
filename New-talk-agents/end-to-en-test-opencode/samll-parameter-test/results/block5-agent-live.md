# Block 5 — Agent / Live

Cross-service smoke: agent session + live shadow evaluation.

## Agent
- Endpoint: `POST /agent/...` (session / chat)
- Expected: agent responds, LLM reachable, broker paper configured

| Check | Expected | Actual | Status |
|---|---|---|---|
| `/agent/health` | ok, LLM reachable | | |
| Broker paper configured | configured: true | | |
| Agent session response | valid reply | | |

## Live shadow evaluation
- Endpoint: `POST /live/...` (shadow evaluation)
- Expected: evaluation executes against paper broker / real endpoint

| Check | Expected | Actual | Status |
|---|---|---|---|
| Shadow evaluation runs | success | | |
| Order path exercised (require_confirmation: false) | order placed / skipped in paper | | |

## Evidence
- `evidence/block5-agent-live/`

## Deviations / Issues
- (link to deviations/issues if any)
