# Requirements — Minimum Things Required to Test (so other agents understand)

> Every field below has **no silent default** — `require_data_root()` `vinu-infra/config.py:22` fail-fast, `require_auth` `vinu-infra/auth.py:29` 401/403, `secrets_loader.py:44` file→env fallback. ATS needs all; Full needs same + `2022-01-01` window + `freeze` + observed halt/Triage.

## API line (9 services, `127.0.0.1` only — not off-machine `docker-compose.yml:1-454`)

| Service | Port | Prefix | Health (open) | Protected example (needs Bearer) |
|---|---|---|---|---|
| news-api | 8080 | `/news` | `GET /news/health` | `GET /news/story/AAPL` |
| stock-api | 8081 | `/stock` | `GET /stock/health` | `GET /stock/candles/AAPL` |
| features-api | 8082 | `/features` | `GET /features/health` | `GET /features/AAPL` |
| initial-analysis-api | 8083 | `/analysis` | `GET /analysis/health` | `GET /analysis/story/AAPL` or `/analysis/angle/shock_clustering/AAPL` |
| quant-core-api | 8084 | `/strategy` + `/simulator` (merged) | `GET /strategy/health` + `GET /simulator/health` | `GET /strategy/strategies` |
| agent-api | 8086 | `/agent` | `GET /agent/health` + `GET /health` (root) | `GET /agent/broker/performance/{artifact_id}` (port 8086, used in `03:111` auth check) |
| research-api | 8087 | `/research` | `GET /research/health` | `GET /research/artifacts?status=PEND` |
| portfolio-api | 8090 | `/portfolio` | `GET /portfolio/health` | `GET /portfolio/state` \| `POST /portfolio/evaluate-batch` |
| live-api | 8091 | `/live` | `GET /live/health` | `POST /live/trade-plan/rebalance-request` |

All `health` are intentionally open (no auth) for Docker `healthcheck`; every other route requires `Authorization: Bearer <VINU_API_KEY>` — custom header name or missing `Bearer` is wrong.

## API keys / secrets (where they live, what file mounts)

- `ALPACA_API_KEY`, `ALPACA_API_SECRET` — **rotated pair**, not leaked `alpaca-details/details.md`; `secrets/alpaca_api_key` + `secrets/alpaca_api_secret` (600) → `/run/secrets/alpaca_api_key` etc. per `docker-compose.yml:436-453`.
- `VINU_LLM_API_KEY` — same `secrets/vinu_llm_api_key` → `/run/secrets/vinu_llm_api_key` (host `host.docker.internal:8009` local `qwen36-35B` vs `openai`).
- `VINU_API_KEY` — any strong `openssl rand -hex 32`, `secrets/vinu_api_key` → `/run/secrets/vinu_api_key` + `env_file: .env` `VINU_API_KEY` (but secret values should be **blank in `.env`**, real in `secrets/*` only per `decisions/13-env-gap-decision.md` — else `docker inspect` leaks).
- Optional: `TELEGRAM_TOKEN` + `VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID`, `DISCORD_TOKEN` + `VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID` — independently optional, left unset still records `SignificanceFlagStore` but nowhere to deliver (`scheduler_workers.py:158`).

Validate before compose:

```bash
scripts/setup-secrets.sh --check   # must print "secret files ready", not FAILED for 4 required
scripts/setup-secrets.sh           # writes ./secrets/* mode 600, what compose mounts
# I: env leak warning — if .env still has secret values, vinu-infra/secrets_loader.py 0fc90e11 will log "also present as plain env" on load_secret; docker inspect <container> | grep VINU_API_KEY should show no plain value
# H: ref_id verification — ticker_ledger.verify_ref_id(ref_id, strategy_store) fail-open logs stale BENCHING→PEND drift
```

## Env (`VINU_*_DATA_ROOT` etc., `env_file: .env` gitignored)

Every `VINU_*_DATA_ROOT` has **no default** — must be `/data` in Docker (`read_only: true` + `./data/<service>:/data` mount, `docker-compose.yml:19-20`). For ATS short window vs Full full window:

- **ATS (fast, 3 tickers):** `VINU_STAGE1_START_DATE=2026-03-01` (6mo, safer) or `2026-06-01` (3mo, fastest) — **must stay BEFORE `2026-07-01` Q3 start** or inverted `[start, Q_T2]` → `no_data` (`vinu-initial-analysis/quarters.py`, `env-example:153`). After ATS, flip to `2022-01-01` for Full.
- **Full (gate):** `VINU_STAGE1_START_DATE=2022-01-01` (origin `04-v2:16`) — keeps `RunLog` `has_existing_run()` + `TickerLedger` comparable across tickers.
- Other: `VINU_SHARED_WATCHLIST_PATH=/shared/watchlist.json` (`data/shared:/shared` mount), `VINU_STOCK_API_URL=http://stock-api:8081` (service DNS, not 127.0.0.1 inside container), `VINU_LLM_BASE_URL=http://host.docker.internal:8009/v1` + `extra_hosts: host.docker.internal:host-gateway` (`docker-compose.yml:38`).

## Watchlist (entry point `04-v2:20` `Gate` reads from)

- `VINU_AGENT_WATCHLIST_SEED_TICKERS=AAPL,MSFT,NVDA` (comma-separated, 3 for ATS) — `scheduler_workers.py:110` `discover_new_tickers` bootstrap via `screener` team; `TickerSummaryStore.list_summaries()` never gains new ticker without this seed.
- Or `data/shared/watchlist.json` synced via `POST /news/watchlist/sync` + `/stock/watchlist/sync` (same `/shared` mount).

## Why this section exists

So any agent (or human) picking up `ats-pattern/04-ats-runbook` or `full-pattern/03-full-runbook` knows **how to test** (which curl line), **why this test** (e.g. rehearsal catches overfit before `risk_gatekeeper` `04-v2:245`), and **what wil happen** (e.g. `rehearsal Sharpe degraded >50% → PaperRehearsal note` vs `PEND → funded ACTIVE` vs `Kill halt → PENDBLOCK`), without inventing endpoint names, header forms, or `run_id` values.
