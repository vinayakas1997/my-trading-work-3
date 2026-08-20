---
name: initial-conditions
status: reference — reflects actual running config, update when it changes
purpose: the concrete facts needed to talk to this running stack — dates, keys, endpoints. Not a log of what happened.
---

# Initial conditions

## Data window (`vinu-initial-analysis`)

| | Value | Where |
|---|---|---|
| Start date | `2022-01-01` | `VINU_STAGE1_START_DATE` in `vinu-components/.env` |
| End date | not fixed — auto-computed as the current calendar-quarter boundary | `vinu-initial-analysis/vinu_initial_analysis/quarters.py::last_completed_period_end()` |

`VINU_TIER2_PERIOD_MONTHS=3` controls the quarter length (must evenly divide
12). The end date is never set manually — it changes only when a calendar
quarter actually closes, which is what keeps `tier2` runs comparable across
tickers and dedupable via `has_existing_run()`.

## Auth — `VINU_API_KEY`

- Value lives at `vinu-components/secrets/vinu_api_key` (also mirrored into
  `.env` as `VINU_API_KEY`, loaded by every container via `env_file`).
- Get it: `cat vinu-components/secrets/vinu_api_key`
- Send it on every request except `/health`:
  ```
  Authorization: Bearer <key>
  ```
- `/health` endpoints are deliberately exempt (no key needed) — that's
  intentional, not a gap.

## Service endpoints

All bound to `127.0.0.1` only (not reachable off this machine).

| Service | Port | Path prefix |
|---|---|---|
| news-api | 8080 | `/news` |
| stock-api | 8081 | `/stock` |
| features-api | 8082 | `/features` |
| initial-analysis-api | 8083 | `/analysis` |
| quant-core-api | 8084 | `/strategy` and `/simulator` (merged container) |
| agent-api | 8086 | `/agent` |
| research-api | 8087 | `/research` |
| portfolio-api | 8090 | `/portfolio` |
| live-api | 8091 | `/live` |

Example real call:
```bash
curl -H "Authorization: Bearer $(cat vinu-components/secrets/vinu_api_key)" \
  http://localhost:8090/portfolio/state
```

## Where config actually lives

- `vinu-components/.env` — all non-secret + secret-fallback config (gitignored).
- `vinu-components/secrets/*` — one file per real credential, what containers
  actually mount at `/run/secrets/<name>` (gitignored).
- `vinu-components/docker-compose.yml` — the real, production-shaped service
  definitions.
- `vinu-components/docker-compose.override.yml` — local-dev-only bind mounts
  for faster iteration; auto-loaded by plain `docker compose up -d`.
