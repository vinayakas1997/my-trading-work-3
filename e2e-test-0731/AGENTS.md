---
name: e2e-test-0731-agents
status: living-document
purpose: entry point for any agent (or person) picking up Stage 1 testing cold
---

# AGENTS.md — Stage 1 E2E Testing

**If you're picking this up cold, read in this order:**
1. This file.
2. [full-plan.md](full-plan.md) — dates, tickers, timeframes, strategies,
   data sources (Alpaca + local LLM), what Stage 1 is and isn't.
3. [scope-responsibilities/](scope-responsibilities/) — one file per
   component: what it does, where its data lives, what it depends on.
4. [architecture.md](architecture.md) — dependency graph + Stage 1
   execution flow as Mermaid diagrams.
5. [testing-status/](testing-status/) — one `test-log.md` per component:
   what will be tested, expected output, and the running Bug-N/Fixed-N
   log. This is where you check what's already been found and fixed
   before assuming something is broken (or working).

## How testing runs

**Everything runs through the Docker Compose stack, not local/CLI
invocation.** `vinu-components/docker-compose.yml` builds all 10 services
from their own Dockerfiles and wires them together via the shared
`vinu-components/.env` (`env_file: .env` on every service block). Do not
use `sync-env.py` for this — that's the local-dev path, explicitly not
used for Stage 1 testing (see project memory / earlier session decision).

```bash
cd vinu-components
docker compose up -d --build     # first run: build + start everything
docker compose ps                # confirm all services are healthy
docker compose logs -f <service> # tail one service's logs
```

Bring services up in dependency order if testing incrementally (see
[architecture.md](architecture.md)'s graph) — `stock-api` and `news-api`
first (no deps), then `features-api`/`initial-analysis-api`, then
`strategy-api`, then `simulator-api`/`research-api`, then
`portfolio-api`. `agent-api` and `live-api` are out of scope for Stage 1
(see their `scope-responsibilities/` files) — don't bring them up unless
specifically testing the Stage 1 consistency check noted in
`testing-status/vinu-agent/test-log.md`.

## The bug/fix loop

1. **Find a bug** while exercising a service's "What will be tested"
   checklist in its `testing-status/<component>/test-log.md`.
2. **Log it immediately as `Bug-N`** in that file's Bug/Fix Log section,
   *before* attempting a fix — symptom, exact reproduction, severity.
   Don't fix first and write a cleaned-up bug report after; the raw
   symptom matters.
3. **Fix the root cause** in the actual service source
   (`vinu-components/<service>/...`), not in the test or the `.env`
   unless the bug genuinely is a config/env problem.
4. **Rebuild the affected container(s) — this is required, not optional.**
   Source code is baked into each image at build time
   (`docker-compose.yml`'s `build:` block); only `./data/<service>` is
   volume-mounted. A plain `docker compose restart <service>` will **not**
   pick up a code change.
   ```bash
   docker compose up -d --build <service>
   ```
   Rebuild only the service(s) you changed, not the whole stack, unless
   the fix touches shared code multiple services import.
5. **Re-run the exact reproduction from `Bug-N`** against the rebuilt
   container. Don't consider it fixed until the original repro actually
   passes.
6. **Log `Fixed-N`** in the same file, immediately following `Bug-N`:
   root cause (confirmed, not guessed), what changed, how it was
   verified, and status (`fixed` / `wontfix` with why / `deferred` with
   why and to when).
7. Move to the next item on the checklist, or the next component.

Full template for `Bug-N`/`Fixed-N` entries lives in
[testing-status/README.md](testing-status/README.md) — follow it exactly
so every component's log reads the same way.

## Rules for this testing pass

- **Docker only.** No direct `pytest`/CLI invocation against a bare
  `python -m vinu_x.server` process for this validation pass — the point
  is to test the same deployment shape Stage 2/3 will actually use.
- **Never run `sync-env.py`.** It's for local/CLI dev, not this Docker-based
  testing pass.
- **Never touch `vinu-components/.env-example`** (leaked-credential file,
  left alone deliberately — see project history). Real credentials live
  only in `vinu-components/.env` (gitignored).
- **`vinu-live` and `vinu-agent`'s broker layer are out of scope for
  Stage 1.** Don't bring them into testing beyond the one documented
  consistency check in `testing-status/vinu-agent/test-log.md`. They
  belong to Stage 2.
- **Don't silently narrow or widen scope.** If a test reveals that
  something in `full-plan.md` or a `scope-responsibilities/` file is
  wrong or has changed, fix the doc as part of the same work — these
  files are supposed to stay accurate, not aspirational.
- **A bug found in one component but caused by another** (e.g.
  `vinu-stock-price` returns malformed candles and breaks `vinu-tools`)
  gets logged in the component that owns the root cause, with a one-line
  cross-reference added to the affected component's file.

## Known environment facts (don't re-derive these)

- Alpaca credentials: `alpaca-details/details.md`, wired into
  `vinu-components/.env`.
- LLM: local OpenAI-compatible server on the **host** at port 8009,
  model `qwen36-35B`, reachable from `news-api`/`research-api`/`agent-api`
  containers via `http://host.docker.internal:8009/v1` (already has
  `extra_hosts: host.docker.internal:host-gateway` in
  `docker-compose.yml` for those three services). **Not yet verified this
  actually connects from inside a running container** — that's a real
  first test item, not an assumption to skip.
- `VINU_RESEARCH_LLM_ENABLED` is now `true` in `.env` (flipped
  2026-07-31, was `false`).
- **The full Docker Compose stack is up and healthy as of 2026-07-31**
  (`docker compose ps` → all 10 services `(healthy)`). Getting there
  required fixing 3 classes of real bugs, logged in detail in each
  affected component's `testing-status/<component>/test-log.md`
  (Bug-1/Fixed-1): (1) `.env` had local-dev-style relative data paths
  (`../data/...`) instead of the Docker-correct `/data` that every
  Dockerfile already defaults to — affected `vinu-news`,
  `vinu-stock-price`, `vinu-tools`, `vinu-strategy`, `vinu-simulator`,
  `vinu-research`; (2) every `./data/<service>` host directory was
  unwritable by the container's non-root user (`uid=100(app) gid=101(app)`)
  — fixed once for all services via
  `docker run --rm -v "$(pwd)/data:/fixdata" alpine chown -R 100:101 /fixdata`
  (no host `sudo` was available, so this went through the Docker daemon
  instead); (3) `vinu-agent` had no data-root default anywhere and fell
  back to an unwritable path — fixed by adding
  `VINU_AGENT_DATA_ROOT=/data` to `.env`. If containers are ever
  recreated from a stale `.env` or fresh `./data`, check for these same
  three failure modes before assuming a new bug.
- **Health check endpoints are NOT `/health` for most services** —
  each service's `vinu_lib.server.create_app` call takes a `route_prefix`
  that changes the real path. Confirmed via grep on each service's
  `server/app.py`:
  - `news-api` (8080) → `/news/health`
  - `stock-api` (8081) → `/stock/health`
  - `features-api` (8082) → `/features/health`
  - `initial-analysis-api` (8083) → `/analysis/health`
  - `strategy-api` (8084) → `/strategy/health`
  - `simulator-api` (8085) → `/simulator/health`
  - `agent-api` (8086) → `/agent/health`
  - `research-api` (8087) → `/research/health`
  - `portfolio-api` (8090) → `/portfolio/health` (direct router prefix,
    not through the shared helper)
  - `live-api` (8091) → `/live/health` (same)
  `docker-compose.yml`'s `healthcheck:` blocks (added 2026-07-31, along
  with `depends_on: {service: {condition: service_healthy}}` on every
  dependency edge, replacing the old start-order-only `depends_on` list)
  already use these correct paths — don't second-guess them without
  re-checking the code first.
- Stage 1 tickers are locked: **AAPL, TSLA, JNJ** (see `full-plan.md`).
- Only 2 of the 3 strategy tiers are `vinu-strategy` YAMLs — both written:
  `vinu-components/vinu-strategy/strategies/e2e_easy_sma_crossover.yaml`
  and `e2e_medium_trend_vol_filter.yaml`. **The complex tier is not a
  `vinu-strategy` YAML at all** — `vinu-strategy`'s DSL can't express an
  LLM call. It runs entirely through `vinu-research`'s
  `POST /trade-plan/{symbol}` instead — see
  `scope-responsibilities/vinu-strategy.md`,
  `scope-responsibilities/vinu-research.md`, and
  `testing-status/vinu-research/test-log.md`. Don't try to write a 4th
  YAML for this — it was considered and deliberately rejected (would test
  a fake lookalike, not the real Step 03 probabilistic-exit machinery).
- No 1-minute candle data is cached anywhere yet — `vinu-stock-price` is
  the first real test item in dependency order for exactly this reason.
