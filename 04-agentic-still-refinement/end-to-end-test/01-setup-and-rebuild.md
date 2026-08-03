---
name: e2e-setup-and-rebuild
status: definition-phase
---

# Step 1 — Rebuild the Stack, Confirm Health, Set the Tickers

## Why this is step 1

Every downstream step in `02` and `03` assumes a clean, fully-built,
healthy stack and a known ticker set. Skipping this and triggering
backfills against a half-rebuilt or stale container is how you end up
debugging a "why is this data missing" problem that's actually just "the
container never picked up the code change." Confirm the foundation first.

## 1. Rebuild every container

From `vinu-components/`:

```bash
docker compose down
docker compose up --build -d
```

All 10 services share `build.context: .` and one `env_file: .env`
(`docker-compose.yml`) — this one command rebuilds and restarts everything.
`depends_on` with `condition: service_healthy` enforces real start order, so
you do not need to start services individually in dependency order
yourself; Compose does it:

news-api, stock-api → features-api → initial-analysis-api →
strategy-api → simulator-api → research-api → portfolio-api →
agent-api → live-api

## 2. Confirm every service is actually healthy, not just running

```bash
docker compose ps
```

Every service should show `healthy`, not just `running` — a service stuck
at `starting` or `unhealthy` will make its dependents fail to start at all
(`depends_on: condition: service_healthy`), so this fails loudly, which is
good: don't proceed past a red service here.

Spot-check a couple of health endpoints directly:

```bash
curl -s http://localhost:8083/analysis/health   # initial-analysis
curl -s http://localhost:8087/research/health   # research
curl -s http://localhost:8086/agent/health      # agent
```

## 3. Confirm the ticker set

The three tickers for this run are `AAPL`, `TSLA`, `JNJ` — already the live
contents of `data/shared/watchlist.json`. Confirm rather than assume:

```bash
cat vinu-components/data/shared/watchlist.json
```

Expected: `{"tickers": ["AAPL", "TSLA", "JNJ"]}` (order doesn't matter). If
it's missing any of the three, either edit the file directly or sync it
into each service via that service's own `POST /watchlist/tickers` route
(each service that has a watchlist concept exposes one — check
`GET /{service}/watchlist/tickers` first to see current state before
overwriting it).

## 4. `.env` sanity check

Confirm `vinu-components/.env` exists (copied from `.env-example`, not the
example file itself) and has real values for:

- `ALPACA_API_KEY` / `ALPACA_API_SECRET` — needed for `vinu-stock-price`'s
  backfill and `vinu-agent`'s broker calls.
- `VINU_LLM_BASE_URL` — needed for `vinu-news` (sentiment), `vinu-research`
  (strategy generation), `vinu-agent` (the agent loop itself). If this
  points to a local model server, confirm that server is actually running
  and reachable at the configured URL *before* triggering anything in `02`
  — a research/news call that silently degrades because the LLM is
  unreachable is a much harder failure to notice than one that fails to
  start at all.

## What to confirm before moving on to `02`

- [ ] `docker compose ps` shows all 10 services `healthy`
- [ ] `data/shared/watchlist.json` contains exactly `AAPL`, `TSLA`, `JNJ`
- [ ] `.env` exists (not just `.env-example`) with real Alpaca + LLM values
- [ ] The configured LLM endpoint responds to a basic request (a plain
      curl/health check against it, not through any vinu-* service)

If any of these fail, stop here — every command in `02` will either error
immediately or silently degrade in a way that's much harder to diagnose
later.
