---
task: 13-secrets-management.md
status: complete
---

# Status: task 13 — move real secrets out of plain `.env` files

## Decision

User chose **self-hosted Docker Compose** (single node, the existing
`docker-compose.yml`). Mechanism: Docker secrets mounted as files, read from
`/run/secrets/<name>` by a new shared loader; `.env` remains for non-secret
config only. A documented manual rotation procedure now exists.

## Files touched

- **`vinu-infra/vinu_infra/secrets_loader.py`** — NEW: `load_secret(secret_name, env_var)`,
  `require_secret(...)`, `secrets_dir()` (`VINU_SECRETS_DIR` override). Resolution order:
  mounted secret file first, legacy env var fallback; empty file → env fallback. Never logs
  values. (Named `secrets_loader`, not `secrets`, because the flat-layout package dir shadows
  stdlib `secrets` and broke starlette's `from secrets import token_hex`.)
- **`vinu-infra/vinu_infra/auth.py`** — `VINU_API_KEY` now resolves through the loader
  (`/run/secrets/vinu_api_key`), so the task-11 internal service-auth key is provisioned via
  this mechanism, not a bespoke `.env` entry (acceptance criterion met).
- **`vinu-infra/vinu_infra/llm/config.py`** — `api_key` via loader (`vinu_llm_api_key`).
- **`vinu-agent/vinu_agent/broker/alpaca.py`** — broker keys via loader (module-level, matching
  prior import-time behavior); also **`tools/options_tool.py`**, **`config.py`** (LLM keys,
  orchestrator key, Telegram/Discord tokens), **`cli.py`** (channel-list status probe).
- **`vinu-research/vinu_research/config.py`** — `llm_api_key` via loader.
- **`vinu-stock-price/vinu_stock/config.py`** + **`providers/tushare.py`**, **`vinu-news/vinu_news/config.py`**
  — POLYGON/ALPACA/TUSHARE/FMP keys via loader.
- **`docker-compose.yml`** — top-level `secrets:` block (9 secrets, files under `./secrets/`,
  gitignored) mounted into the services that need them: `vinu_api_key` → portfolio/live/agent;
  broker+data keys → agent/news/stock; `vinu_llm_api_key` → agent/research; tokens → agent.
  Validated with `docker compose config`.
- **`scripts/setup-secrets.sh`** — NEW, idempotent bootstrap: populates `./secrets/*` (0600)
  from existing files / shell env / `.env`, empty file = env fallback (stack still boots).
- **`docs/secrets-rotation.md`** — NEW: resolution rules, credential→file→env table, first-time
  deploy, rotation steps (edit file + `up -d --force-recreate`), leaked-credential playbook.
- **`.gitignore`** — added `alpaca-details/` and `secrets/`.
- **`alpaca-details/details.md`** — `git rm --cached` (removed from index; still on disk).

## What is achieved

- A single, documented secrets resolution path (`vinu_infra.secrets_loader`) that the
  task-11 internal auth key and every real broker/LLP/notification credential now go through;
  in the deployed (Docker) environment none of them come from plain-text `.env`.
- The one **active leak** found by the audit — real-looking Alpaca keys committed in
  `alpaca-details/details.md` — was removed from the index and gitignored. **Action still
  required: rotate those keys at Alpaca** (they remain in git history).

## Testing

- `vinu-infra/tests`: **109 passed** (99 + 10 new `test_secrets_loader.py`).
- `vinu-agent/tests`: **841 passed, 4 skipped**.
- `vinu-research/tests`: **628 passed, 1 skipped**.
- `vinu-stock-price/tests`: **44 passed** (standalone; needs no env).
- `vinu-news/tests`: 120 passed with `VINU_NEWS_DATA_ROOT` set; 1 pre-existing LLM-dependent
  failure (`test_api_v1 ... llm-sentiment-classifier-alternatives`) confirmed identical on the
  stashed (pre-change) tree — not caused by this task.
- End-to-end smoke: with `VINU_SECRETS_DIR` pointed at a dir holding the secret files,
  `auth.VINU_API_KEY`, `alpaca.API_KEY`, and `LlmConfig.from_env().api_key` all returned the
  file values with the env vars absent; file-wins-over-env verified.
- `docker compose config` passes (with a `.env` present).

## Alignment with acceptance criteria

- Real broker/LLM credentials no longer read from plain `.env` in the deployed environment
  (they come from mounted secret files); local dev keeps the env-var fallback, cleanly separated
  by the loader's resolution order. ✓
- Task-11 `VINU_API_KEY` is provisioned through the mechanism (`/run/secrets/vinu_api_key`). ✓
- A documented rotation procedure exists (`docs/secrets-rotation.md`). ✓

## Notes / deliberate choices

- Single-node compose file-based secrets are not encrypted at rest on the host; that matches the
  chosen "self-hosted Docker Compose" option and is documented. Upgrading to a real secrets
  manager later is a loader-internal swap (no consumer changes).
- Access logging: Docker file secrets don't emit read logs. The loader is the single choke
  point, so adding an audit read-log there (or behind a TOML/env flag) is a one-file change;
  deferred to avoid overhead in the default path.
- `VINU_LLM_FALLBACKS` remains env-based by design (structured JSON); documented in the rotation
  doc.
- Real values are never committed: `secrets/` is gitignored, and the setup script writes 0600.