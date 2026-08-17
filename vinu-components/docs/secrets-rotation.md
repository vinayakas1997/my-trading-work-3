# Secrets management & rotation procedure (implementation-plan task 13)

Deployment target: **self-hosted Docker Compose** (single node). Real
credentials are Docker secrets mounted as files and read by services from
`/run/secrets/<name>` via `vinu_infra.secrets_loader.load_secret` — **not**
from plain-text `.env`.

## How a secret is resolved

For every credential, the loader looks, in order:

1. `/run/secrets/<secret_name>` — the Docker secret file (deployed path)
2. the legacy env var (local dev / non-secret override)

An **empty** secret file falls back to the env var, so a partially-populated
`./secrets/` dir never hard-crashes the stack. Secret files are never logged;
the loader returns only the string.

### Credential → secret file → env var

| Credential                    | Secret file (`./secrets/…`)      | Legacy env var                  | Consumers |
|-------------------------------|----------------------------------|----------------------------------|-----------|
| Internal service-auth key     | `vinu_api_key`                   | `VINU_API_KEY`                   | portfolio-api, live-api (enforce), agent-api (consume) |
| Alpaca API key                | `alpaca_api_key`                 | `ALPACA_API_KEY`                 | agent-api (broker/tools), news-api, stock-api |
| Alpaca API secret             | `alpaca_api_secret`              | `ALPACA_API_SECRET`              | same as above |
| Polygon data key              | `polygon_api_key`                | `POLYGON_API_KEY`                | stock-api |
| Financial Modeling Prep key   | `fmp_api_key`                    | `FMP_API_KEY`                    | news-api |
| Tushare token                 | `tushare_token`                  | `TUSHARE_TOKEN`                  | stock-api |
| LLM provider key              | `vinu_llm_api_key`               | `VINU_LLM_API_KEY`               | agent-api, research-api, vinu-infra llm |
| Telegram bot token            | `telegram_token`                 | `TELEGRAM_TOKEN`                 | agent-api |
| Discord bot token             | `discord_token`                  | `DISCORD_TOKEN`                  | agent-api |

Note: `VINU_LLM_FALLBACKS` (agent JSON array of alternative providers) stays
env-based — its keys are part of a structured value; if you run fallback
providers in production, prefer a single `vinu_llm_api_key` primary and keep
the fallback keys in a mounted secret file passed via an env indirection.

## Deploying (first time)

```bash
cd vinu-components
cp .env-example .env            # fill non-secret config; credentials optional
scripts/setup-secrets.sh        # creates ./secrets/* from .env or prompts
docker compose up -d
```

`scripts/setup-secrets.sh` writes each secret file mode `0600` under
`./secrets/` (gitignored). It never overwrites an already-populated file, so
it is idempotent.

## Rotating a credential

1. Generate the new value (rotate the key at the provider first).
2. Edit the corresponding `./secrets/<name>` file (e.g. `./secrets/alpaca_api_key`).
3. Recreate the affected services:
   ```bash
   docker compose up -d --force-recreate <service>   # or the whole stack
   ```
4. Verify the new value is in effect (e.g. an authenticated endpoint returns
   200, or `vinu-agent channel list` reports the channel configured).

Because keys are read at process start (module import time), a rotation always
requires a container recreate — there is no live-reload.

## Leaked credential playbook

If a credential ever lands in git (a committed `.env`, a pasted key in a doc,
etc.):

1. **Rotate the key at the provider immediately** — anything committed to git
   history must be treated as public. Deleting it is not enough.
2. Remove it from tracking and ignore it:
   ```bash
   git rm --cached <file>
   # add the path to .gitignore
   ```
3. If the file is small and no one has pushed it yet, rewrite history
   (`git filter-repo` / `filter-branch`); otherwise coordinate a force-push
   with all collaborators and rotate regardless.

Example already handled: `alpaca-details/details.md` (real-looking Alpaca key
pair, previously tracked) was removed from the index and `alpaca-details/` is
now gitignored — **rotate those keys**.

## What is deliberately NOT secret-gated

Feature flags, ports, URLs, paths, thresholds (`VINU_*` non-credential vars)
stay in `.env`/`.env-example` — the loader only covers credentials, so the
compose `env_file: .env` block still carries all non-secret config.