# Decision — Row 13 env_file gap (accepted risk 2026-09-07)

> `docker-compose.yml:9` `env_file: .env` + `secrets: file: ./secrets/*`.

## Decision

- Accepted risk in writing for current deployment: `env_file: .env` remains for `VINU_*_DATA_ROOT` etc., but **real secrets must live only in `./secrets/*` (600) + `/run/secrets/<name>`**, `.env` secret values left blank. `secrets_loader.py:44` file→env fallback kept, but plain-env `docker inspect` leaks if `.env` filled.
- Future fix (backlog): remove secret keys from `env_file` list and mount `VINU_SECRETS_DIR` override for host runs.

## Dated

- 2026-09-07 — accepted with mitigation (secrets files, not .env values).
