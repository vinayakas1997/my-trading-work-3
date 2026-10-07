# Current settings, guards and configuration, by component

Generated 2026-10-07 from three sources: the services' source code (every setting name a service reads, and the default written in code), the project template `.env-example`, and the values the **running containers** hold. The real `.env` file was **not read** (it holds secrets). Secret settings are listed by name only.

How to read the columns:
- **Code default:** what the code uses when nothing sets the value.
- **Deployed:** what the running container holds. `<not set>` means the code default applies.
- **Why:** the reason. It comes from a curated note, or from the comment written in the project template (marked), or is shown as _reason not yet written_ instead of being guessed.

Things this inventory shows (read first):
1. **Every container receives the whole shared `.env`.** Each service sees every other service's settings. Which service really reads a setting is only known from the code, which is why the tables below come from the code.
2. **The deployed profile turns most live guards on** (entry guards, precondition enforcing, daily allocation, exits exempt from halts, out-of-distribution detector at `alert`, maturity gating). The connection manifest still says "default off": that is the code default, not what is deployed.
3. **A temporary test override is deployed:** `VINU_STAGE1_START_DATE=2026-06-17` (analysis window start), which the template says to revert before real use.
4. **Regular-hours assumptions remain** in settings (`VINU_CORRELATION_MARKET_HOURS_ONLY`, `VINU_CORRELATION_SESSION_BREAK_ON_CLOSE`, one spread limit and one price-age limit for all sessions, backtest spread of 0).
5. Some settings are read through a helper that builds the name from a prefix, so they do not appear as a literal in the code; they are listed in the last section from the template.

Services covered: 12 plus the shared library. Settings found in code: 482.

---

## llm-gateway (port 8099)

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_GATEWAY_MAX_ATTEMPTS` | `"3"` | `<not set>` | _reason not yet written_ |
| `VINU_LLM_MAX_TOKENS` | `"8000"` | `<not captured>` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_GATEWAY_AGE_STEP_SEC` | `"300"` | `<not set>` | _reason not yet written_ |
| `VINU_LLM_GATEWAY_ATTEMPT_TIMEOUT_SEC` | `"300"` | `<not set>` | _reason not yet written_ |
| `VINU_LLM_GATEWAY_DEADLINE_SEC` | `"1800"` | `<not set>` | _reason not yet written_ |
| `VINU_LLM_GATEWAY_HISTORY_JSON_DAYS` | `"7"` | `<not set>` | _reason not yet written_ |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_UPSTREAM_URL` | `cls.upstream_url` | `http://host.docker.internal:8092/v1` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_GATEWAY_DATA_ROOT` | `"data"` | `/data` | _reason not yet written_ |

### Models and LLM

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_GATEWAY_SLOTS` | `"1"` | `<not set>` | The local model serves one request at a time, so the gateway runs one call at a time. |

### Secrets (names only, values never shown)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_UPSTREAM_KEY_REF` | `""` | `<secret: name only>` | _reason not yet written_ |

---

## stock-api (port 8081)

### Guards and on/off switches

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_EVENTS_MACRO_ENABLED` | `-` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_GAP_REFILL_THRESHOLD` | `"0"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_STOCK_LOAD_MEMORY_LIMIT` | `"512MB"` | `<not set>` | _reason not yet written_ |
| `VINU_STOCK_MAX_CONCURRENT_LOADS` | `"2"` | `<not set>` | _reason not yet written_ |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_EVENTS_REFRESH_HOURS` | `"20"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_STOCK_POLL_INTERVAL_SEC` | `str(DEFAULT_POLL_INTERVAL_SEC` | `60` | VINU_STOCK_DATA_ROOT is the source of truth for the service's data root. vinu-stock-price no longer trusts the persisted `vinu_settings.data_root` row at startup -- a stale value there (e.g. a Windows host path seeded by a prior host-side run) used to silently (project template) |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `ALPACA_DATA_BASE_URL` | `-` | `https://data.alpaca.markets` | _reason not yet written_ |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SHARED_ROOT` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_SHARED_WATCHLIST_PATH` | `""` | `/shared/watchlist.json` | `/shared/watchlist.json` in Docker -- news-api and stock-api both bind-mount `./data/shared:/shared` in docker-compose.yml. Left blank, `sync_watchlist_ from_shared()`/`POST /news/stock/watchlist/sync` fail with "VINU_SHARED_ WATCHLIST_PATH not set" instead of (project template) |
| `VINU_STOCK_DATA_ROOT` | `-` | `/data` | VINU_STOCK_DATA_ROOT is the source of truth for the service's data root. vinu-stock-price no longer trusts the persisted `vinu_settings.data_root` row at startup -- a stale value there (e.g. a Windows host path seeded by a prior host-side run) used to silently (project template) |
| `VINU_STOCK_META_DB_PATH` | `-` | `/data/meta.db` | _reason not yet written_ |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_STOCK_HOST` | `DEFAULT_HOST` | `127.0.0.1` | VINU_STOCK_DATA_ROOT is the source of truth for the service's data root. vinu-stock-price no longer trusts the persisted `vinu_settings.data_root` row at startup -- a stale value there (e.g. a Windows host path seeded by a prior host-side run) used to silently (project template) |
| `VINU_STOCK_PORT` | `str(DEFAULT_PORT` | `8081` | VINU_STOCK_DATA_ROOT is the source of truth for the service's data root. vinu-stock-price no longer trusts the persisted `vinu_settings.data_root` row at startup -- a stale value there (e.g. a Windows host path seeded by a prior host-side run) used to silently (project template) |

### Secrets (names only, values never shown)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `ALPACA_API_KEY` | `-` | `<secret: name only>` | _reason not yet written_ |
| `ALPACA_API_SECRET` | `-` | `<secret: name only>` | _reason not yet written_ |
| `FINNHUB_API_KEY` | `-` | `<secret: name only>` | Finnhub free tier (60 req/min): earnings + economic (FOMC/CPI/NFP/PCE) calendars for the vinu-events blackout guard (how-to-make-it-live.md #2, Stage 4). Empty => vinu-events still runs but skips the calendar poll and the entry guard stays inert (fail-open). G (project template) |
| `POLYGON_API_KEY` | `-` | `<secret: name only>` | _reason not yet written_ |
| `TUSHARE_TOKEN` | `-` | `<secret: name only>` | _reason not yet written_ |

### Other

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_PROVIDER_ORDER` | `""` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_STOCK_DEFAULT_PROVIDER` | `DEFAULT_PROVIDER` | `alpaca` | VINU_STOCK_DATA_ROOT is the source of truth for the service's data root. vinu-stock-price no longer trusts the persisted `vinu_settings.data_root` row at startup -- a stale value there (e.g. a Windows host path seeded by a prior host-side run) used to silently (project template) |
| `VINU_STOCK_DEFAULT_SESSION` | `-` | `<not set>` | Unset means regular hours, so every caller that does not ask for a session keeps the old behaviour. |
| `VINU_STOCK_LOAD_THREADS` | `"2"` | `<not set>` | _reason not yet written_ |
| `VINU_STOCK_OVERNIGHT_FEED` | `"boats"` | `<not set>` | Feed used for the overnight session (Blue Ocean, 15-minute delay, from 2024-09-16). Empty turns overnight data off. |

---

## news-api (port 8080)

### Guards and on/off switches

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_NEWS_MODE` | `DEFAULT_MODE` | `ticker` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_NEWS_MAX_WORKERS` | `str(DEFAULT_MAX_WORKERS` | `8` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_NEWS_POLL_INTERVAL_SEC` | `str(DEFAULT_POLL_INTERVAL_SEC` | `600` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_NEWS_DATABASE_URL` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_STOCK_API_URL` | `DEFAULT_STOCK_API_URL` | `http://stock-api:8081` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_NEWS_DB_PATH` | `-` | `/data/news.db` | _reason not yet written_ |
| `VINU_NEWS_STORAGE` | `"sqlite"` | `sqlite` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |
| `VINU_SHARED_WATCHLIST_PATH` | `""` | `/shared/watchlist.json` | `/shared/watchlist.json` in Docker -- news-api and stock-api both bind-mount `./data/shared:/shared` in docker-compose.yml. Left blank, `sync_watchlist_ from_shared()`/`POST /news/stock/watchlist/sync` fail with "VINU_SHARED_ WATCHLIST_PATH not set" instead of (project template) |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_NEWS_HOST` | `DEFAULT_HOST` | `0.0.0.0` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |
| `VINU_NEWS_PORT` | `str(DEFAULT_PORT` | `8080` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |

### Secrets (names only, values never shown)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `ALPACA_API_KEY` | `-` | `<secret: name only>` | _reason not yet written_ |
| `ALPACA_API_SECRET` | `-` | `<secret: name only>` | _reason not yet written_ |
| `FMP_API_KEY` | `-` | `<secret: name only>` | _reason not yet written_ |

### Other

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_NEWS_ACTIVE_TIERS` | `DEFAULT_ACTIVE_TIERS` | `1,2,3,4` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |

---

## features-api (port 8082)

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_STOCK_API_URL` | `"http://127.0.0.1:8081"` | `http://stock-api:8081` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_FEATURES_DATA_DIR` | `"./data"` | `/data` | _reason not yet written_ |
| `VINU_FEATURES_META_DB_PATH` | `""` | `/data/meta.db` | _reason not yet written_ |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_FEATURES_HOST` | `"127.0.0.1"` | `127.0.0.1` | _reason not yet written_ |
| `VINU_FEATURES_PORT` | `"8082"` | `8082` | _reason not yet written_ |

---

## initial-analysis-api (port 8083)

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_CACHE_MAXSIZE` | `"256"` | `<not set>` | _reason not yet written_ |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_CACHE_TTL_SEC` | `"300"` | `<not set>` | _reason not yet written_ |
| `VINU_COMPUTE_POLL_INTERVAL_SEC` | `"3600"` | `<not set>` | _reason not yet written_ |
| `VINU_STAGE1_START_DATE` | `"2022-01-01"` | `2026-06-17` | TEMPORARY override (2026-06-17) left from the small end-to-end check; the template says to revert to 2022-01-01 before real use. |
| `VINU_TIER2_PERIOD_MONTHS` | `"3"` | `3` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_NEWS_API_URL` | `"http://localhost:8080"` | `http://news-api:8080` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_RESEARCH_API_URL` | `"http://localhost:8087"` | `http://research-api:8087` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STOCK_API_URL` | `"http://localhost:8081"` | `http://stock-api:8081` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_INITIAL_ANALYSIS_HOST` | `"0.0.0.0"` | `<not set>` | _reason not yet written_ |
| `VINU_INITIAL_ANALYSIS_PORT` | `"8083"` | `<not set>` | _reason not yet written_ |

---

## quant-core-api (port 8084)

### Guards and on/off switches

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SIMULATOR_ALLOW_SHORT` | `str(DEFAULT_ALLOW_SHORT` | `true` | _reason not yet written_ |

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_CORRELATION_API_URL` | `DEFAULT_CORRELATION_API_URL` | `http://initial-analysis-api:8083` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_SIMULATOR_DEVIATION_THRESHOLD` | `str(DEFAULT_DEVIATION_THRESHOLD` | `0.05` | _reason not yet written_ |
| `VINU_SIMULATOR_INITIAL_CAPITAL` | `str(DEFAULT_INITIAL_CAPITAL` | `1000000.0` | Starting capital of a backtest. |
| `VINU_SIMULATOR_SLIPPAGE_PCT` | `str(DEFAULT_SLIPPAGE_PCT` | `0.0005` | Slippage assumed by the backtest (0.05 percent). |
| `VINU_SIMULATOR_TRANSACTION_COST_PCT` | `str(DEFAULT_TRANSACTION_COST_PCT` | `0.001` | Cost per trade assumed by the backtest (0.1 percent). |
| `VINU_SIM_QUEUE_PCT` | `"0"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_SIM_SPREAD_BPS` | `"0"` | `<not set>` | Spread assumed by the backtest. Zero means backtests ignore the spread, which flatters extended-hours results. |
| `VINU_STRATEGY_CASH_FLOOR` | `str(DEFAULT_CASH_FLOOR` | `0.10` | vinu-strategy and vinu-simulator now share one container (quant-core-api, Group 1 fold, component-consolidation-plan.md) -- each keeps its own data-root subdirectory so they don't collide on one shared /data. (project template) |
| `VINU_STRATEGY_MAX_WEIGHT` | `str(DEFAULT_MAX_WEIGHT` | `0.25` | vinu-strategy and vinu-simulator now share one container (quant-core-api, Group 1 fold, component-consolidation-plan.md) -- each keeps its own data-root subdirectory so they don't collide on one shared /data. (project template) |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SIMULATOR_OHCLV_CACHE_TTL_SEC` | `"120"` | `<not set>` | _reason not yet written_ |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_FEATURES_API_URL` | `DEFAULT_FEATURES_API_URL` | `http://features-api:8082` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STOCK_API_URL` | `DEFAULT_STOCK_API_URL` | `http://stock-api:8081` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STRATEGY_API_URL` | `DEFAULT_STRATEGY_API_URL` | `http://quant-core-api:8084` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SHARED_WATCHLIST_PATH` | `""` | `/shared/watchlist.json` | `/shared/watchlist.json` in Docker -- news-api and stock-api both bind-mount `./data/shared:/shared` in docker-compose.yml. Left blank, `sync_watchlist_ from_shared()`/`POST /news/stock/watchlist/sync` fail with "VINU_SHARED_ WATCHLIST_PATH not set" instead of (project template) |
| `VINU_SIMULATOR_DATA_ROOT` | `""` | `/data/simulator` | _reason not yet written_ |
| `VINU_STRATEGY_DATA_ROOT` | `""` | `/data/strategy` | vinu-strategy and vinu-simulator now share one container (quant-core-api, Group 1 fold, component-consolidation-plan.md) -- each keeps its own data-root subdirectory so they don't collide on one shared /data. (project template) |
| `VINU_STRATEGY_STRATEGIES_DIR` | `""` | `/data/strategy/strategies` | vinu-strategy and vinu-simulator now share one container (quant-core-api, Group 1 fold, component-consolidation-plan.md) -- each keeps its own data-root subdirectory so they don't collide on one shared /data. (project template) |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SIMULATOR_HOST` | `DEFAULT_HOST` | `127.0.0.1` | _reason not yet written_ |
| `VINU_SIMULATOR_PORT` | `str(DEFAULT_PORT` | `8085` | _reason not yet written_ |
| `VINU_STRATEGY_HOST` | `DEFAULT_HOST` | `127.0.0.1` | vinu-strategy and vinu-simulator now share one container (quant-core-api, Group 1 fold, component-consolidation-plan.md) -- each keeps its own data-root subdirectory so they don't collide on one shared /data. (project template) |
| `VINU_STRATEGY_PORT` | `str(DEFAULT_PORT` | `8084` | vinu-strategy and vinu-simulator now share one container (quant-core-api, Group 1 fold, component-consolidation-plan.md) -- each keeps its own data-root subdirectory so they don't collide on one shared /data. (project template) |

### Other

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SIMULATOR_BENCHMARK_TICKERS` | `""` | `SPY,QQQ` | _reason not yet written_ |
| `VINU_STRATEGY_REBALANCE_FREQ` | `DEFAULT_REBALANCE_FREQ` | `daily` | vinu-strategy and vinu-simulator now share one container (quant-core-api, Group 1 fold, component-consolidation-plan.md) -- each keeps its own data-root subdirectory so they don't collide on one shared /data. (project template) |

---

## screener-api (port 8095)

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SCREENER_PAIRLIST_TTL_SEC` | `"60.0"` | `<not set>` | New Stage B service (rule-based full-market scanner). VINU_SCREENER_DATA_ROOT is set to /data by the Dockerfile already (same read-only-root-plus-one- writable-mount pattern every other service uses); the rule/audit DBs default under it unless overridden below (project template) |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_AGENT_API_URL` | `""` | `http://agent-api:8086` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STOCK_API_URL` | `"http://localhost:8081"` | `http://stock-api:8081` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SCREENER_AUDIT_DB` | `str(DEFAULT_DATA_ROOT / "screener_audit.db"` | `<not set>` | New Stage B service (rule-based full-market scanner). VINU_SCREENER_DATA_ROOT is set to /data by the Dockerfile already (same read-only-root-plus-one- writable-mount pattern every other service uses); the rule/audit DBs default under it unless overridden below (project template) |
| `VINU_SCREENER_DATA_ROOT` | `str(Path.home(` | `/screener-data` | New Stage B service (rule-based full-market scanner). VINU_SCREENER_DATA_ROOT is set to /data by the Dockerfile already (same read-only-root-plus-one- writable-mount pattern every other service uses); the rule/audit DBs default under it unless overridden below (project template) |
| `VINU_SCREENER_RANKER_CHURN_DB` | `str(DEFAULT_DATA_ROOT / "screener_ranker_churn.db"` | `<not set>` | New Stage B service (rule-based full-market scanner). VINU_SCREENER_DATA_ROOT is set to /data by the Dockerfile already (same read-only-root-plus-one- writable-mount pattern every other service uses); the rule/audit DBs default under it unless overridden below (project template) |
| `VINU_SCREENER_RANKER_DB` | `str(DEFAULT_DATA_ROOT / "screener_rankers.db"` | `<not set>` | New Stage B service (rule-based full-market scanner). VINU_SCREENER_DATA_ROOT is set to /data by the Dockerfile already (same read-only-root-plus-one- writable-mount pattern every other service uses); the rule/audit DBs default under it unless overridden below (project template) |
| `VINU_SCREENER_RANKER_SNAPSHOT_DB` | `str(DEFAULT_DATA_ROOT / "screener_ranker_snapshots.db"` | `<not set>` | New Stage B service (rule-based full-market scanner). VINU_SCREENER_DATA_ROOT is set to /data by the Dockerfile already (same read-only-root-plus-one- writable-mount pattern every other service uses); the rule/audit DBs default under it unless overridden below (project template) |
| `VINU_SCREENER_RULE_DB` | `str(DEFAULT_DATA_ROOT / "screener_rules.db"` | `<not set>` | New Stage B service (rule-based full-market scanner). VINU_SCREENER_DATA_ROOT is set to /data by the Dockerfile already (same read-only-root-plus-one- writable-mount pattern every other service uses); the rule/audit DBs default under it unless overridden below (project template) |
| `VINU_SHARED_ROOT` | `""` | `<not set>` | _reason not yet written_ |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SCREENER_HOST` | `"0.0.0.0"` | `<not set>` | _reason not yet written_ |
| `VINU_SCREENER_PORT` | `"8095"` | `<not set>` | _reason not yet written_ |

### Secrets (names only, values never shown)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SCREENER_PAIRLIST_TOKEN` | `-` | `<secret: name only>` | New Stage B service (rule-based full-market scanner). VINU_SCREENER_DATA_ROOT is set to /data by the Dockerfile already (same read-only-root-plus-one- writable-mount pattern every other service uses); the rule/audit DBs default under it unless overridden below (project template) |

### Other

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_SCREENER_SEED_CONFIG` | `-` | `<not set>` | _reason not yet written_ |

---

## research-api (port 8087)

### Guards and on/off switches

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_RESEARCH_ALLOW_SHORT` | `"true"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_CALIBRATED_CONFIDENCE_IN_EV_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_CONFIDENCE_RELIABILITY_LOG_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_DEBATE_SIGNAL_ENABLED` | `-` | `true` | Consumer half of the bull/bear/risk_officer adversarial debate -- pairs with VINU_AGENT_DEBATE_MODE below, both must be on together. (project template) |
| `VINU_RESEARCH_DECAY_RESPONSE_MODE` | `"auto"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_FORECAST_PROMPT_EXTRA_CONTEXT_ENABLED` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). Out-of-distribution detector: first rung only (log). halt / flatten are earned by watching this one in paper. Trust is earned: capital and the agent (project template) |
| `VINU_RESEARCH_GENERATOR_MODE` | `"hybrid"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_LLM_ENABLED` | `"false"` | `true` | _reason not yet written_ |
| `VINU_RESEARCH_MATURITY_TIER_ENABLED` | `-` | `true` | _reason not yet written_ |
| `VINU_RESEARCH_OPTIONS_IV_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_PAPER_REHEARSAL_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_PROMOTION_CORRELATION_REQUIRED` | `-` | `<not set>` | Promotion needs the correlation check against existing strategies to pass. |
| `VINU_RESEARCH_PROMOTION_HOLDOUT_REQUIRED` | `-` | `<not set>` | Promotion needs the holdout test to pass. |
| `VINU_RESEARCH_PROMOTION_PBO_REQUIRED` | `-` | `<not set>` | Promotion needs a probability-of-backtest-overfitting result; waived only when too few results exist to compute it (waiver is stored). |
| `VINU_RESEARCH_PROMOTION_STRESS_TEST_REQUIRED` | `-` | `<not set>` | Promotion needs the stress test to pass. |
| `VINU_RESEARCH_REFINE_PROMPT_FULL_METRICS_ENABLED` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). Out-of-distribution detector: first rung only (log). halt / flatten are earned by watching this one in paper. Trust is earned: capital and the agent (project template) |
| `VINU_RESEARCH_REGIME_ANALOGUE_ENABLED` | `-` | `true` | _reason not yet written_ |
| `VINU_RESEARCH_STRESS_TEST_ENABLED` | `"true"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MODE` | `"off"` | `<not set>` | _reason not yet written_ |
| `VINU_SWEEP_DIVERSITY_REQUIRED` | `"true"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_CORRELATION_API_URL` | `DEFAULT_CORRELATION_API_URL` | `http://initial-analysis-api:8083` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_LLM_MAX_TOKENS` | `str(DEFAULT_LLM_MAX_TOKENS` | `<not captured>` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |
| `VINU_RESEARCH_CONFIDENCE_CALIBRATION_MIN_SAMPLES` | `"30"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_DEBATE_SIGNAL_WEIGHT` | `"1.0"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_HOLDOUT_FRACTION` | `"0.2"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_IMPROVEMENT_THRESHOLD` | `str(DEFAULT_IMPROVEMENT_THRESHOLD` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_INITIAL_CAPITAL` | `str(DEFAULT_INITIAL_CAPITAL` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_MAX_DRAWDOWN_THRESHOLD` | `"-0.25"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_MAX_HOLDOUT_SHARPE_DEGRADATION` | `"0.5"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_MAX_ITERATIONS` | `str(DEFAULT_MAX_ITERATIONS` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_MIN_TRADES_FOR_PASS` | `"30"` | `<not set>` | Fewest trades a strategy needs to pass: fewer cannot support the statistics (decision 2026-10-07). |
| `VINU_RESEARCH_PAPER_REHEARSAL_MAX_DEGRADATION` | `"0.5"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. (project template) |
| `VINU_RESEARCH_PORTFOLIO_BETA_MAX_RATIO` | `"1.5"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_PROMOTION_CORRELATION_THRESHOLD` | `"0.85"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_PROMOTION_DSR_THRESHOLD` | `"0.95"` | `<not set>` | Deflated Sharpe the strategy must reach to be promoted. |
| `VINU_RESEARCH_PROMOTION_PBO_THRESHOLD` | `"0.7"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_REGIME_SIZE_TILT_BOUND` | `"0.3"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_SCREENER_RANK_SIZE_TILT_BOUND` | `"0.3"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_SLIPPAGE_PCT` | `"0.0005"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_STRESS_TEST_MAX_DD` | `"-0.50"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_SWEEP_GRID_MAX_POINTS` | `"20"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |
| `VINU_RESEARCH_TARGET_MAX_DRAWDOWN` | `"-0.30"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_TARGET_SHARPE` | `"1.5"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_TRADE_SCORE_CALIBRATION_BOUND` | `"0.2"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MIN_SAMPLE` | `"30"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_TRANSACTION_COST_PCT` | `"0.001"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_WF_MIN_COMPLETED_WINDOWS` | `"2"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_WF_MIN_TRAIN_DAYS` | `"252"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_WF_STABILITY_THRESHOLD` | `"0.5"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_WF_TEST_PCT` | `"0.2"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_WF_TRAIN_PCT` | `"0.6"` | `<not set>` | _reason not yet written_ |
| `VINU_SWEEP_HYPEROPT_MAX_POINTS` | `"8"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |
| `VINU_SWEEP_MIN_SUCCEEDS_FOR_PASS` | `"2"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |
| `VINU_WALK_FORWARD_MAX_CONCURRENCY` | `"3"` | `<not set>` | _reason not yet written_ |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_TIMEOUT_SEC` | `"120.0"` | `300` | Per-call timeout for the local model; long prompts hit it when thinking is on. |
| `VINU_PBO_EMBARGO_PERIODS` | `"0"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_RESEARCH_HOLDOUT_GAP_DAYS` | `"5"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_INTERVAL` | `"1d"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_LLM_TTL_SEC` | `str(DEFAULT_LLM_TTL_SEC` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_PAPER_REHEARSAL_LOOKBACK_DAYS` | `"7"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. (project template) |
| `VINU_RESEARCH_PORTFOLIO_BETA_LOOKBACK_DAYS` | `"60"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_REGIME_RECOMPUTE_INTERVAL_DAYS` | `"1"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_REVALIDATION_INTERVAL_DAYS` | `"30"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_REVALIDATION_LOOKBACK_DAYS` | `"180"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_STRESS_DERIVE_REGIME_WINDOWS` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_WF_GAP_DAYS` | `"5"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |
| `VINU_RESEARCH_WF_WINDOWS` | `"3"` | `<not set>` | _reason not yet written_ |
| `VINU_SWEEP_INTERVALS` | `"1d,4h,1h,15m"` | `<not set>` | Bar sizes every idea is researched on. Must agree with the bar sizes the validator tests. |
| `VINU_SWEEP_TOP_N_PER_INTERVAL` | `"3"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_AGENT_API_URL` | `DEFAULT_AGENT_API_URL` | `http://agent-api:8086` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_FEATURES_API_URL` | `DEFAULT_FEATURES_API_URL` | `http://features-api:8082` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_LLM_BASE_URL` | `DEFAULT_LLM_BASE_URL` | `http://llm-gateway:8099/v1` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |
| `VINU_SCREENER_API_URL` | `DEFAULT_SCREENER_API_URL` | `http://screener-api:8095` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_SIMULATOR_API_URL` | `DEFAULT_SIMULATOR_API_URL` | `http://quant-core-api:8084` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STOCK_PRICE_API_URL` | `DEFAULT_STOCK_PRICE_API_URL` | `http://stock-api:8081` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_RESEARCH_AGENT_DATA_ROOT` | `-` | `/data` | _reason not yet written_ |
| `VINU_RESEARCH_DATA_ROOT` | `""` | `/data` | _reason not yet written_ |
| `VINU_RESEARCH_LIVE_DATA_ROOT` | `-` | `/live-data` | _reason not yet written_ |
| `VINU_STRATEGY_EVAL_DATA_ROOT` | `""` | `/strategy-eval` | _reason not yet written_ |
| `VINU_TRADE_SCORE_CALIBRATION_HISTORY` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_TRADE_SCORE_CALIBRATION_STATE` | `-` | `<not set>` | _reason not yet written_ |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_RESEARCH_HOST` | `DEFAULT_HOST` | `127.0.0.1` | _reason not yet written_ |
| `VINU_RESEARCH_PORT` | `str(DEFAULT_PORT` | `8087` | _reason not yet written_ |

### Models and LLM

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_MODEL` | `DEFAULT_LLM_MODEL` | `/models/Qwen3.5-9B-Q4_K_M.gguf` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |
| `VINU_RESEARCH_LLM_CANDIDATES` | `"3"` | `<not set>` | _reason not yet written_ |

### Secrets (names only, values never shown)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_API_KEY` | `-` | `<secret: name only>` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |

### Other

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_RESEARCH_BENCHMARK_SYMBOL` | `DEFAULT_BENCHMARK_SYMBOL` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_CONFLUENCE_EXCLUDES_FORECAST_CONFIDENCE` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). Out-of-distribution detector: first rung only (log). halt / flatten are earned by watching this one in paper. Trust is earned: capital and the agent (project template) |
| `VINU_RESEARCH_REGIME_ANALOGUE_BENCHMARK_SYMBOL` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_SCREENER_RANKER_ID` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_SESSION` | `"regular"` | `<not set>` | Session a single research run uses when none is given; regular keeps old behaviour. |
| `VINU_RESEARCH_WALK_FORWARD` | `"true"` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_WF_METHOD` | `"expanding"` | `<not set>` | _reason not yet written_ |
| `VINU_SWEEP_USE_HYPEROPT` | `"true"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |
| `VINU_SWEEP_USE_VECTORBT` | `"true"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |
| `VINU_SWEEP_VECTORBT_CONCURRENCY` | `"5"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |
| `VINU_VALIDATION_SESSIONS` | `"regular,all"` | `<not set>` | Every bar size is tested under regular hours and under all 24 hours; the 24-hour result gives the per-session risk hints. |

---

## portfolio-api (port 8090)

### Guards and on/off switches

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_PORTFOLIO_ALLOCATION_MODE` | `"hrp"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_PORTFOLIO_MATURITY_CAPITAL_GATING_ENABLED` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). Out-of-distribution detector: first rung only (log). halt / flatten are earned by watching this one in paper. Trust is earned: capital and the agent (project template) |
| `VINU_PORTFOLIO_MATURITY_MULT_PAPER_ONLY` | `"0.25"` | `<not set>` | _reason not yet written_ |

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_CORRELATION_API_URL` | `DEFAULT_ANALYSIS_API_URL` | `http://initial-analysis-api:8083` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_PORTFOLIO_ABS_LOSS_HALT` | `"0.0"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_CLUSTER_CORR_THRESHOLD` | `"0.8"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_PORTFOLIO_CONFIDENCE_TILT_BOUND` | `"0.3"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_DD_FLAT` | `"-0.15"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_PORTFOLIO_DD_HALVE` | `"-0.10"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_PORTFOLIO_DRAWDOWN_HALT` | `"-0.20"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_GAME_PLAN_READINESS_THRESHOLD` | `"0.5"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_MATURITY_MULT_COLD_START` | `"0.1"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_MATURITY_MULT_EARLY_LIVE` | `"0.5"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_MAX_ACTION` | `"0.20"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_PORTFOLIO_MAX_CORRELATED_CLUSTER_WEIGHT` | `"0.6"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_PORTFOLIO_MAX_PER_SECTOR` | `"0.4"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_MAX_PER_STRATEGY` | `"0.3"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_MIN_CALIBRATION_ENTRIES` | `"5"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_MIN_WEIGHT_CHANGE` | `"0.02"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_PORTFOLIO_OUTCOME_TILT_BOUND` | `"0.3"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_PROMOTION_DSR_THRESHOLD` | `"0.95"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_REGIME_TILT_BOUND` | `"0.3"` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_RESERVE_FRACTION` | `"0.0"` | `0.10` | Share of equity kept undeployed. |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_PORTFOLIO_DRAWDOWN_INTERVAL_SEC` | `"300"` | `<not set>` | _reason not yet written_ |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_AGENT_API_URL` | `DEFAULT_AGENT_API_URL` | `http://agent-api:8086` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_RESEARCH_API_URL` | `DEFAULT_RESEARCH_API_URL` | `http://research-api:8087` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_SIMULATOR_API_URL` | `DEFAULT_SIMULATOR_API_URL` | `http://quant-core-api:8084` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STOCK_PRICE_API_URL` | `DEFAULT_STOCK_API_URL` | `http://stock-api:8081` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STRATEGY_API_URL` | `DEFAULT_STRATEGY_API_URL` | `http://quant-core-api:8084` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_PORTFOLIO_DATA_ROOT` | `str(DEFAULT_DATA_ROOT` | `/data` | _reason not yet written_ |
| `VINU_PORTFOLIO_TAGS_PATH` | `str(DEFAULT_TAGS_PATH` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_DATA_ROOT` | `""` | `/data` | _reason not yet written_ |
| `VINU_SHARED_ROOT` | `""` | `<not set>` | _reason not yet written_ |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_PORTFOLIO_HOST` | `DEFAULT_HOST` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_PORT` | `str(DEFAULT_PORT` | `<not set>` | _reason not yet written_ |

### Other

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_PORTFOLIO_BENCHMARK_SYMBOL` | `DEFAULT_BENCHMARK_SYMBOL` | `<not set>` | _reason not yet written_ |
| `VINU_PORTFOLIO_PER_SYMBOL_REGIME` | `"false"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |

---

## live-api (port 8091)

### Guards and on/off switches

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_EXEC_IDEMPOTENCY_ENABLED` | `"true"` | `true` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_ABORT_ON_EQUITY_READ_FAILURE` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_BROKER_UNREACHABLE_NOTIFY_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_DECISION_CLOSED_BARS_ONLY` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_DECISION_NOVELTY_ENABLED` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_DECISION_REQUIRE_VALIDATED_STRATEGY` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_DECISION_SIGNAL_OUTCOMES_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_EXECUTION_FILL_ENRICHMENT_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_EXECUTION_LOG_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_HALT_POLICY` | `"entries_only"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_OOD_DETECTOR` | `"off"` | `alert` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_ORDER_ROUTING_MODE` | `"market"` | `<not set>` | How live orders are routed. Code default is market. The order guard refuses market orders outside regular hours, so this needs a session-aware choice for the 24-hour system. |
| `VINU_LIVE_PRECONDITION_ENFORCING_ENABLED` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_RISK_GATEKEEPER_MATURITY_SCALING_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_RUNTIME_CORR_ENABLED` | `-` | `true` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_SCHEDULER_BREAKER_USES_BROKER_ACCOUNT` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_SCHEDULER_ENTRY_GUARDS_ENABLED` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_SCHEDULER_EXITS_EXEMPT_FROM_HALTS` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_SCHEDULER_RESPECT_TRADE_PLAN_SYMBOLS` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_SIGNAL_CONFLICT_POLICY` | `"block"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_THESIS_RECHECK_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_RISK_CVAR_ENABLED` | `-` | `true` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_RISK_FORECAST_SCALING_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_RISK_VOL_TARGET_ENABLED` | `-` | `true` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LESSON_MIN_TRADES` | `"30"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LESSON_STAR_MIN` | `"50"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_COOLDOWN_LOSSES` | `"2"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_DECISION_MAX_TRIGGER_ATTEMPTS` | `"3"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_DECISION_NOVELTY_MIN_REFERENCE` | `"30"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_DECISION_NOVELTY_RATIO` | `"2.0"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_LARGE_ORDER_PARTICIPATION_PCT` | `"0.01"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_MAX_HOLD_DAYS` | `"30"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_MAX_SLIPPAGE_PCT` | `"0.001"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_MAX_SPREAD_BPS` | `"25"` | `<not set>` | Block an entry when the bid/ask spread is wider than this. One number for all sessions. |
| `VINU_LIVE_OOD_CORR` | `"0.95"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_OOD_MIN_SIGNALS` | `"2"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_OOD_TURBULENCE_MULT` | `"5.0"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_PASSIVE_LIMIT_OFFSET_BPS` | `"5"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_PRICE_MAX_AGE_HOURS` | `"96"` | `<not set>` | Pause entries when the newest bar is older than this. 96 tolerates a long weekend on daily bars; too loose for intraday strategies. |
| `VINU_LIVE_RECONCILE_MAX_RATIO` | `"10.0"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_RUNTIME_CORR_COOLDOWN_SEC` | `"3600"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_RUNTIME_CORR_REDUCE_PCT` | `"0.25"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_RUNTIME_CORR_THRESHOLD` | `"0.85"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_SIGNAL_MAX_AGE_HOURS` | `"72"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_SLIPPAGE_BUDGET_FRACTION` | `"0.5"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_SYMBOL_LOCKOUT_LOSSES` | `"0"` | `3` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_TRAILING_ACTIVATION_PCT` | `"0.0"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_TRAILING_ATR_MULT` | `"2.0"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_RISK_CVAR_THRESHOLD` | `"0.03"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_RISK_FORECAST_SCALING_FLOOR` | `"0.5"` | `<not set>` | _reason not yet written_ |
| `VINU_RISK_VOL_TARGET` | `"0.15"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_SHADOW_AUTO_PAUSE_SHARPE` | `"-1.0"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_SHADOW_MIN_PAPER_DAYS` | `str(min_paper_days` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_SHADOW_MIN_PAPER_DAYS_1D` | `str(min_paper_days_1d if min_paper_days_1d is not None else ` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_SHADOW_MIN_PAPER_DAYS_1H` | `str(min_paper_days_1h if min_paper_days_1h is not None else ` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LIVE_BROKER_STALE_SEC` | `"180"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_COOLDOWN_HOURS` | `"24"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_DECISION_AGENT_TIMEOUT_SEC` | `"300"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_DECISION_FEATURE_WINDOW_BARS` | `"0"` | `600` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_DECISION_POLL_INTERVAL` | `"60"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_DECISION_POSITION_REVIEW_CADENCE_BARS` | `"5"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_EVENT_BLACKOUT_HOURS` | `"24"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_FEEDBACK_INTERVAL` | `"300"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_FILL_CONFIRM_DELAY_SEC` | `"0.7"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_INTERVAL` | `"3600"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_RECONCILE_SETTLE_SEC` | `"12"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_SHADOW_INTERVAL` | `"3600"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_SYMBOL_LOCKOUT_HOURS` | `"72"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_THESIS_RECHECK_COOLDOWN_SEC` | `"3600"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_TRADE_PLAN_APPROVAL_INTERVAL` | `"300"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_TRADE_PLAN_INTERVAL` | `"300"` | `<not set>` | _reason not yet written_ |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_AGENT_API_URL` | `DEFAULT_AGENT_API_URL` | `http://agent-api:8086` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_INITIAL_ANALYSIS_API_URL` | `-` | `http://initial-analysis-api:8083` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_PORTFOLIO_API_URL` | `DEFAULT_PORTFOLIO_API_URL` | `http://portfolio-api:8090` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_RESEARCH_API_URL` | `DEFAULT_RESEARCH_API_URL` | `http://research-api:8087` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STOCK_PRICE_API_URL` | `DEFAULT_STOCK_PRICE_API_URL` | `http://stock-api:8081` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STRATEGY_API_URL` | `DEFAULT_STRATEGY_API_URL` | `http://quant-core-api:8084` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LIVE_BOOK_LOCK_PATH` | `-` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_DATA_ROOT` | `str(DEFAULT_DATA_ROOT` | `/data` | _reason not yet written_ |
| `VINU_SHARED_ROOT` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_STRATEGY_EVAL_DATA_ROOT` | `""` | `/strategy-eval` | _reason not yet written_ |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LIVE_HOST` | `DEFAULT_HOST` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_PORT` | `str(DEFAULT_PORT` | `<not set>` | _reason not yet written_ |

### Other

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LIVE_BROKER_UNREACHABLE_RENOTIFY_CYCLES` | `"6"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_DECISION_NOVELTY_REFERENCE_ROWS` | `"250"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_DECISION_SIGNAL_HORIZON_BARS` | `"20"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_ENTRY_TWAP_SLICES` | `"3"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_EXECUTION_FILL_ENRICHMENT_BATCH` | `"25"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_EXECUTION_STYLE` | `"twap"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_FALLBACK_PORTFOLIO_VALUE` | `"1000000.0"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_FILL_CONFIRM_ATTEMPTS` | `"3"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_OOD_MOVE` | `"0.10"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_OOD_VOL` | `"0.08"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_PARTIAL_FILL_TOLERANCE` | `"0.02"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_RECONCILE_AUTOCORRECT` | `-` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_LIVE_SCHEDULER_ADOPTED_SYMBOLS` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_SCHEDULER_USE_DAILY_ALLOCATION` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). (project template) |
| `VINU_LIVE_SHARE_PRECISION` | `"0"` | `<not set>` | _reason not yet written_ |
| `VINU_LIVE_TURBULENCE_VOL` | `"0.05"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |

---

## agent-api (port 8086)

### Guards and on/off switches

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_AGENT_DEBATE_MODE` | `"off"` | `full` | Producer half of the bull/bear/risk_officer adversarial debate (investment_committee.yaml swarm) -- pairs with VINU_RESEARCH_DEBATE_SIGNAL_ENABLED above. (project template) |
| `VINU_AGENT_GUARD_SOFT_LIMITS` | `"false"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_LIVE_DECISION_MATURITY_SCALING_ENABLED` | `-` | `true` | Exits can never be trapped by a halt, and the breaker sees the broker account (also on by default in code now). Out-of-distribution detector: first rung only (log). halt / flatten are earned by watching this one in paper. Trust is earned: capital and the agent (project template) |
| `VINU_LIVE_HALT_POLICY` | `"entries_only"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_RISK_CVAR_ENABLED` | `"false"` | `true` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_RISK_FORECAST_SCALING_ENABLED` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_RISK_VOL_TARGET_ENABLED` | `"false"` | `true` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_AGENT_ANGLE_COVERAGE_MAX_DEFERRALS` | `"3"` | `<not set>` | watchlist-seed knob above -- this one is not about which tickers enter the pipeline, it's about WHEN a ticker already in it is allowed to move from vinu-initial-analysis into angle comprehension) --- vinu-initial-analysis writes a new run_id per ANGLE, not onc (project template) |
| `VINU_AGENT_ANGLE_COVERAGE_MIN_FRACTION` | `"0.0"` | `<not set>` | watchlist-seed knob above -- this one is not about which tickers enter the pipeline, it's about WHEN a ticker already in it is allowed to move from vinu-initial-analysis into angle comprehension) --- vinu-initial-analysis writes a new run_id per ANGLE, not onc (project template) |
| `VINU_AGENT_ATR_STOP_MULTIPLE` | `"2.0"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_CALIBRATION_MIN_ACCURACY` | `"0.45"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_CALIBRATION_MIN_ENTRIES` | `"3"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_CAPITAL_ALLOCATOR_BUDGET` | `"100000"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL` | `"900"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_DAILY_LIMIT_DB` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_GUARD_REAUTH_FRACTION` | `"1.0"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_KELLY_FRACTION` | `"0.25"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_MAX_ITERATIONS` | `"50"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_MAX_TOOL_RESULT_CHARS` | `"100000"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_NOTIFY_QUIET_MIN_SEVERITY` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_RISK_GATEKEEPER_INTERVAL` | `"900"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_RISK_PER_TRADE_PCT` | `"0.02"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_SYMBOL_LIMIT_DB` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_LLM_MAX_TOKENS` | `"8000"` | `<not captured>` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |
| `VINU_RESEARCH_MIN_ATTEMPTS` | `"3"` | `<not set>` | Attempts per ticker before the manager may give up (counted by backtest-runner delegations). |
| `VINU_RISK_CVAR_THRESHOLD` | `"0.03"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_RISK_FORECAST_SCALING_FLOOR` | `"0.5"` | `<not set>` | _reason not yet written_ |
| `VINU_RISK_VOL_TARGET` | `"0.15"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_SWARM_MAX_ITERATIONS` | `"25"` | `<not set>` | _reason not yet written_ |
| `VINU_SWARM_MAX_WORKERS` | `"4"` | `<not set>` | _reason not yet written_ |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_AGENT_NOTIFY_COOLDOWN_SEC` | `0.0` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_NOTIFY_DEDUP_WINDOW_SEC` | `0.0` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_NOTIFY_RESERVATION_TTL_SEC` | `30.0` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_ORDER_THROTTLE_PER_SEC` | `"10"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_ORDER_THROTTLE_WINDOW_SEC` | `"1.0"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_PLANNER_INTERVAL` | `"1800"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_SIGNIFICANCE_INTERVAL` | `"900"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_SKILL_AUDIT_INTERVAL` | `"3600"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_TOOL_TIMEOUT` | `"60"` | `900` | Whole sub-agent delegation timeout, longer than one LLM call because a delegation makes several. |
| `VINU_BAR_VALIDATION_TIMEOUT_SEC` | `"3600"` | `<not set>` | How long the all-bar-sizes validation may take. |
| `VINU_DEBRIEF_ORDER_LOOKBACK` | `"50"` | `<not set>` | _reason not yet written_ |
| `VINU_LLM_CONTEXT_WINDOW` | `"0"` | `<not set>` | _reason not yet written_ |
| `VINU_LLM_TIMEOUT` | `"120"` | `<not set>` | _reason not yet written_ |
| `VINU_ORCHESTRATOR_LLM_CONTEXT_WINDOW` | `"0"` | `<not set>` | Leave all of these unset and the orchestrator transparently shares the VINU_LLM_* config above with teams/specialists (today's default behavior). Set ANY one of these to opt the orchestrator into its own, separately-configured provider/model -- e.g. a real Ope (project template) |
| `VINU_ORCHESTRATOR_LLM_TIMEOUT` | `"120"` | `<not set>` | Leave all of these unset and the orchestrator transparently shares the VINU_LLM_* config above with teams/specialists (today's default behavior). Set ANY one of these to opt the orchestrator into its own, separately-configured provider/model -- e.g. a real Ope (project template) |
| `VINU_SIGNIFICANCE_MUTE_HOURS` | `str(hours` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_STAGE1_START_DATE` | `"2022-01-01"` | `2026-06-17` | TEMPORARY override (2026-06-17) left from the small end-to-end check; the template says to revert to 2022-01-01 before real use. |
| `VINU_SWARM_TIMEOUT` | `"300"` | `<not set>` | _reason not yet written_ |
| `VINU_SWEEP_INTERVALS` | `DEFAULT_INTERVALS` | `<not set>` | Bar sizes every idea is researched on. Must agree with the bar sizes the validator tests. |
| `VINU_SWEEP_TOP_N_PER_INTERVAL` | `_os.environ.get("VINU_SWEEP_TOP_N", str(top_n` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. (project template) |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `ALPACA_DATA_BASE_URL` | `"https://data.alpaca.markets"` | `https://data.alpaca.markets` | _reason not yet written_ |
| `VINU_INITIAL_ANALYSIS_API_URL` | `"http://localhost:8083"` | `http://initial-analysis-api:8083` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_LIVE_API_URL` | `"http://localhost:8091"` | `http://live-api:8091` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_LLM_BASE_URL` | `""` | `http://llm-gateway:8099/v1` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |
| `VINU_NEWS_API_URL` | `"http://localhost:8080"` | `http://news-api:8080` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_ORCHESTRATOR_LLM_BASE_URL` | `""` | `<not set>` | Leave all of these unset and the orchestrator transparently shares the VINU_LLM_* config above with teams/specialists (today's default behavior). Set ANY one of these to opt the orchestrator into its own, separately-configured provider/model -- e.g. a real Ope (project template) |
| `VINU_PORTFOLIO_API_URL` | `"http://localhost:8090"` | `http://portfolio-api:8090` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_REFLECTION_API_URL` | `"http://localhost:8092"` | `http://reflection-worker:8092` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_RESEARCH_API_URL` | `"http://localhost:8087"` | `http://research-api:8087` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_SCREENER_API_URL` | `"http://localhost:8095"` | `http://screener-api:8095` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_SIMULATOR_API_URL` | `"http://localhost:8084"` | `http://quant-core-api:8084` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STOCK_PRICE_API_URL` | `"http://localhost:8081"` | `http://stock-api:8081` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_STRATEGY_API_URL` | `"http://localhost:8084"` | `http://quant-core-api:8084` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |
| `VINU_TOOLS_API_URL` | `"http://localhost:8082"` | `http://features-api:8082` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_AGENT_AUDIT_LEDGER` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_AUDIT_LOG` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_DATA_ROOT` | `Path.home(` | `/data` | Must be /data in Docker -- agent-api's container is read_only: true with only /data (bind-mounted from ./data/agent) and tmpfs /tmp, /home/app/.cache writable. Without this set, config.py/kill_switch.py fall back to Path.home()/".vinu", which is not a writable (project template) |
| `VINU_AGENT_MEMORY_DIR` | `str(data_root / "memory"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_NOTIFY_DELIVERY_LOG` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_ORCHESTRATOR_DIR` | `str(Path(__file__` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_SESSIONS_DIR` | `str(data_root / "sessions"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_SKILLS_DIR` | `os.environ.get("VINU_AGENT_SKILLS_PATH", str(Path(__file__` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_SKILLS_PATH` | `str(Path(__file__` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_SYMBOL_OVERRIDE_DB` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_TEAMS_DIR` | `str(Path(__file__` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_USER_SKILLS_DIR` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_RESEARCH_DATA_ROOT` | `""` | `/data` | _reason not yet written_ |
| `VINU_STRATEGY_EVAL_DATA_ROOT` | `""` | `/strategy-eval` | _reason not yet written_ |

### Models and LLM

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_FALLBACKS` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_LLM_MODEL` | `"gpt-4o-mini"` | `/models/Qwen3.5-9B-Q4_K_M.gguf` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |
| `VINU_LLM_PROVIDER` | `"openai"` | `openai` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |
| `VINU_ORCHESTRATOR_LLM_MODEL` | `"gpt-4o-mini"` | `<not set>` | Leave all of these unset and the orchestrator transparently shares the VINU_LLM_* config above with teams/specialists (today's default behavior). Set ANY one of these to opt the orchestrator into its own, separately-configured provider/model -- e.g. a real Ope (project template) |
| `VINU_ORCHESTRATOR_LLM_PROVIDER` | `"openai"` | `<not set>` | Leave all of these unset and the orchestrator transparently shares the VINU_LLM_* config above with teams/specialists (today's default behavior). Set ANY one of these to opt the orchestrator into its own, separately-configured provider/model -- e.g. a real Ope (project template) |

### Secrets (names only, values never shown)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `ALPACA_API_KEY` | `-` | `<secret: name only>` | _reason not yet written_ |
| `ALPACA_API_SECRET` | `-` | `<secret: name only>` | _reason not yet written_ |
| `VINU_LLM_API_KEY` | `-` | `<secret: name only>` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |
| `VINU_ORCHESTRATOR_LLM_API_KEY` | `-` | `<secret: name only>` | Leave all of these unset and the orchestrator transparently shares the VINU_LLM_* config above with teams/specialists (today's default behavior). Set ANY one of these to opt the orchestrator into its own, separately-configured provider/model -- e.g. a real Ope (project template) |

### Other

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `ALPACA_PAPER` | `"true"` | `true` | Owner rule: broker is Alpaca PAPER only. Not to change until the paper run has been judged. |
| `VINU_AGENT_BROKER_PROVIDER` | `DEFAULT_PROVIDER` | `<not set>` | Which real broker `broker/factory.py`'s get_live_broker() constructs. "alpaca" is the only real provider today and the default -- leave unset unless/until a second provider is actually added to broker/factory.py's _PROVIDERS registry. (project template) |
| `VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID` | `""` | `<not set>` | Telegram/Discord are independently optional -- set either, both, or neither. Left unset, significance-worker still detects and records flags (SignificanceFlagStore), it just has nowhere to deliver them. TELEGRAM_TOKEN: bot token from @BotFather. VINU_AGENT_TEL (project template) |
| `VINU_AGENT_DISCORD_URGENT_CHANNEL_ID` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_NOTIFY_QUIET_END_HOUR` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_NOTIFY_QUIET_START_HOUR` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_POSITION_SIZING_METHOD` | `"fractional_kelly"` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_SCREENER_RANKER_ID` | `""` | `core_starter` | Which screener ranker the planner takes its tickers from; unset means the planner has nothing to work on. |
| `VINU_AGENT_SCREENER_TOP_N` | `"10"` | `10` | How many top tickers per cycle (the vision's top 10). |
| `VINU_AGENT_SUMMARY_PARALLELISM` | `"3"` | `1` | One: the local model serves one request at a time, parallel tickers only make each wait longer. |
| `VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID` | `""` | `<not set>` | Telegram/Discord are independently optional -- set either, both, or neither. Left unset, significance-worker still detects and records flags (SignificanceFlagStore), it just has nowhere to deliver them. TELEGRAM_TOKEN: bot token from @BotFather. VINU_AGENT_TEL (project template) |
| `VINU_AGENT_TELEGRAM_URGENT_CHAT_ID` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_AGENT_WATCHLIST_SEED_TICKERS` | `""` | `<not set>` | TickerSummaryStore.list_summaries() (every scheduled worker's watchlist source) never gains a genuinely new ticker on its own -- every writer is only ever invoked FOR a ticker already in that store. This comma- separated seed list is the one place a new ticker (project template) |
| `VINU_SKILL_VERSION` | `""` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_SWEEP_TOP_N` | `str(top_n` | `<not set>` | _reason not yet written_ |

---

## reflection-worker (port none)

### Guards and on/off switches

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_REFLECTION_BRAIN_SYNTHESIS_ENABLED` | `-` | `<not set>` | _reason not yet written_ |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_REFLECTION_BRAIN_SYNTHESIS_INTERVAL_SEC` | `"3600"` | `<not set>` | _reason not yet written_ |
| `VINU_REFLECTION_WORKER_INTERVAL_SEC` | `str(DEFAULT_WORKER_INTERVAL_SEC` | `<not set>` | _reason not yet written_ |
| `VINU_TIER2_PERIOD_MONTHS` | `str(DEFAULT_TIER2_PERIOD_MONTHS` | `3` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LIVE_TRADE_AUDIT_LOG` | `str(Path.cwd(` | `/live-data/trade_audit_log.jsonl` | _reason not yet written_ |
| `VINU_REFLECTION_AGENT_DATA_ROOT` | `str(Path.cwd(` | `/agent-data` | _reason not yet written_ |
| `VINU_REFLECTION_DATA_ROOT` | `str(Path.cwd(` | `/data` | _reason not yet written_ |
| `VINU_REFLECTION_INITIAL_ANALYSIS_DATA_ROOT` | `str(Path.cwd(` | `/initial-analysis-data` | _reason not yet written_ |
| `VINU_REFLECTION_PORTFOLIO_DATA_ROOT` | `str(Path.cwd(` | `/portfolio-data` | _reason not yet written_ |
| `VINU_REFLECTION_STOCK_DATA_ROOT` | `str(Path.cwd(` | `/stock-data` | _reason not yet written_ |
| `VINU_RESEARCH_DATA_ROOT` | `""` | `/data` | _reason not yet written_ |
| `VINU_SCREENER_DATA_ROOT` | `str(Path.cwd(` | `/screener-data` | New Stage B service (rule-based full-market scanner). VINU_SCREENER_DATA_ROOT is set to /data by the Dockerfile already (same read-only-root-plus-one- writable-mount pattern every other service uses); the rule/audit DBs default under it unless overridden below (project template) |
| `VINU_STRATEGY_EVAL_DATA_ROOT` | `""` | `/strategy-eval` | _reason not yet written_ |
| `VINU_TRADE_SCORE_CALIBRATION_HISTORY` | `""` | `<not set>` | _reason not yet written_ |

### Network (host and port)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_REFLECTION_HOST` | `DEFAULT_HOST` | `<not set>` | _reason not yet written_ |
| `VINU_REFLECTION_PORT` | `str(DEFAULT_PORT` | `<not set>` | _reason not yet written_ |

---

## shared (vinu-infra)

### Guards and on/off switches

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_MODELS_ENABLED` | `True` | `false` | False: the models container stays dormant (owner rule), so model angles are skipped. |

### Limits and thresholds

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LIVE_RUNTIME_CORR_THRESHOLD` | `"0.85"` | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |

### Timing and schedules

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_MODEL_SERVICE_TIMEOUT_SEC` | `DEFAULT_TIMEOUT_SEC` | `<not set>` | _reason not yet written_ |

### Connections to other services

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_MODEL_SERVICE_URL` | `-` | `http://models-api:8096` | Docker Compose service-name hostnames (see docker-compose.yml's `services:` block) -- NOT 127.0.0.1. Inside a container, 127.0.0.1 means "myself," not another container; only the service DNS name reaches another container on the Compose network. If you ever ru (project template) |

### Storage and paths

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_CALIBRATION_LOG` | `-` | `/data/calibration_log.jsonl` | _reason not yet written_ |
| `VINU_CHRONOS_CHECKPOINT` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_DATA_ROOT` | `str(Path.home(` | `<not set>` | _reason not yet written_ |
| `VINU_EDGE_DATA_ROOT` | `"VINU_STRATEGY_EVAL_DATA_ROOT"` | `<not set>` | _reason not yet written_ |
| `VINU_KRONOS_CHECKPOINT` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_LLM_ROLES_PATH` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_LOG_FILE` | `"/tmp/logs/vinu-trace.log" if _DEBUG else ""` | `<not set>` | _reason not yet written_ |
| `VINU_MODELS_DIR` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_NEWS_DB_PATH` | `-` | `/data/news.db` | _reason not yet written_ |
| `VINU_SECRETS_DIR` | `"/run/secrets"` | `<not set>` | _reason not yet written_ |
| `VINU_STRATEGY_EVAL_DATA_ROOT` | `""` | `/strategy-eval` | _reason not yet written_ |
| `VINU_STRUCTURED_LOG` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_TIMER_TIMERXL_CHECKPOINT` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_TIMESFM_CHECKPOINT` | `-` | `<not set>` | _reason not yet written_ |
| `VINU_TRADE_AUDIT_LOG` | `-` | `/data/trade_audit_log.jsonl` | _reason not yet written_ |

### Models and LLM

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_LLM_ENABLE_THINKING` | `""` | `false` | Off: hidden thinking used about 70 percent of tokens and long prompts timed out. |
| `VINU_LLM_ROLE` | `-` | `<not set>` | _reason not yet written_ |

### Secrets (names only, values never shown)

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_API_KEY` | `""` | `<secret: name only>` | Internal service-to-service key. Empty means every internal route is open. |
| `VINU_LLM_API_KEY` | `-` | `<secret: name only>` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |

### Other

| Setting | Code default | Deployed | Why |
|---|---|---|---|
| `VINU_CORS_ORIGINS` | `""` | `<not set>` | _reason not yet written_ |
| `VINU_DEBUG` | `"false"` | `false` | _reason not yet written_ |
| `VINU_DEBUG_LEVEL` | `"1"` | `1` | _reason not yet written_ |
| `VINU_RECORDING_TIME_FORMAT` | `"15min"` | `<not set>` | _reason not yet written_ |

---

## Declared in the template but read through a prefix helper (no literal name in code)

| Setting | Likely service | Deployed | Why |
|---|---|---|---|
| `DEFAULT_MIN_OBSERVATIONS` | shared | `<not set>` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `HINDSIGHT_LLM_CTX_SIZE` | hindsight-llm (separate compose file) | `<not set>` | not part of the main `docker compose up`) --- Any strong random string (e.g. `openssl rand -hex 32`), same value used by both hindsight-db and hindsight-app in docker-compose-hindsight.yml. Pin to a real released tag once you've picked one -- see https://githu (project template) |
| `HINDSIGHT_LLM_MODEL_FILE` | hindsight-llm (separate compose file) | `<not set>` | not part of the main `docker compose up`) --- Any strong random string (e.g. `openssl rand -hex 32`), same value used by both hindsight-db and hindsight-app in docker-compose-hindsight.yml. Pin to a real released tag once you've picked one -- see https://githu (project template) |
| `HINDSIGHT_LLM_N_GPU_LAYERS` | hindsight-llm (separate compose file) | `<not set>` | not part of the main `docker compose up`) --- Any strong random string (e.g. `openssl rand -hex 32`), same value used by both hindsight-db and hindsight-app in docker-compose-hindsight.yml. Pin to a real released tag once you've picked one -- see https://githu (project template) |
| `HINDSIGHT_LLM_PARALLEL` | hindsight-llm (separate compose file) | `<not set>` | not part of the main `docker compose up`) --- Any strong random string (e.g. `openssl rand -hex 32`), same value used by both hindsight-db and hindsight-app in docker-compose-hindsight.yml. Pin to a real released tag once you've picked one -- see https://githu (project template) |
| `HINDSIGHT_VERSION` | hindsight-llm (separate compose file) | `<not set>` | not part of the main `docker compose up`) --- Any strong random string (e.g. `openssl rand -hex 32`), same value used by both hindsight-db and hindsight-app in docker-compose-hindsight.yml. Pin to a real released tag once you've picked one -- see https://githu (project template) |
| `VINU_CORRELATION_BASELINE_WINDOW_DAYS` | initial-analysis-api | `7` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_CACHE_MAXSIZE` | initial-analysis-api | `128` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_CACHE_TTL_SEC` | initial-analysis-api | `300` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_COMPACT_THRESHOLD` | initial-analysis-api | `50` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_COMPUTE_POLL_INTERVAL_SEC` | initial-analysis-api | `3600` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_DRAWDOWN_LOOKBACK_HOURS` | initial-analysis-api | `24` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_DRAWDOWN_MIN_PCT` | initial-analysis-api | `-3.0` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_IMPACT_HIGH_THRESHOLD` | initial-analysis-api | `2.0` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_IMPACT_MEDIUM_THRESHOLD` | initial-analysis-api | `0.5` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_MARKET_HOURS_ONLY` | initial-analysis-api | `true` | Analysis restricts to market hours; this is a regular-hours assumption to review for the 24-hour system. |
| `VINU_CORRELATION_PORT` | initial-analysis-api | `8083` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_CORRELATION_SESSION_BREAK_ON_CLOSE` | initial-analysis-api | `true` | Analysis breaks series at the close; a regular-hours assumption to review. |
| `VINU_DECAY_FORGET_DAYS` | shared | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_DECAY_RATIO` | shared | `<not set>` | Names here match code exactly. Uncomment + restart to change, no rebuild. Sweep: intervals 1d,1H,15min top3 each = 9 per ticker. 1d runs first. Paper rehearsal: trailing window + max Sharpe degradation. PBO embargo: boundary periods dropped per OOS block, 0 ke (project template) |
| `VINU_INITIAL_ANALYSIS_DATA_ROOT` | initial-analysis-api | `/data` | `VINU_CORRELATION_DATA_ROOT` (this template's previous name here) is not read anywhere in vinu_initial_analysis's code -- the real variable is `VINU_INITIAL_ANALYSIS_DATA_ROOT`. Renamed to match; harmless in practice so far only because the Dockerfile's own `/ (project template) |
| `VINU_LLM_ANALYSIS_CONCURRENCY` | llm-gateway | `3` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |
| `VINU_LLM_ANALYSIS_MODE` | llm-gateway | `auto` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |
| `VINU_LLM_TTL_SEC` | llm-gateway | `86400` | Local OpenAI-compatible server running on the HOST at port 8009. host.docker.internal (not 127.0.0.1) is required so containers can reach it -- news-api, research-api, and agent-api all already have `extra_hosts: host.docker.internal:host-gateway` set in docke (project template) |
| `VINU_LSTM_MIN_OBSERVATIONS` | shared | `<not set>` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |
| `VINU_NEWS_DATA_ROOT` | news-api | `/data` | Data-root/db-path values below (this section through vinu-research) must be `/data`-rooted in Docker -- every service's container is `read_only: true` with only its own `./data/<service>:/data` bind mount (plus tmpfs /tmp, /home/app/.cache) writable, same reas (project template) |
| `VINU_TIMESFM_MAX_CONTEXT` | shared | `<not set>` | New-talk-/Final-implementation/04-first-small-E2E-check/plan.md) -- a short ~2-week window instead of the full 2022-01-01-to-now history, so the check is fast to run. Revert to the real value above (uncomment it, delete/comment this line) before any real/produ (project template) |

Settings still without a written reason: 255. They are listed so they can be filled in, not hidden.
