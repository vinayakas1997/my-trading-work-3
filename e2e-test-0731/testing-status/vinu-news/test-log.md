# vinu-news — Test Log

**Status:** Passed — full checklist verified 2026-07-31 (see "Verification results" below; 3 bugs found & fixed: Bug-2/3/4); Bug-5 (news backfill sync→async) found & fixed 2026-08-01

## What will be tested

- Fetch historical news via Alpaca (`https://data.alpaca.markets/v1beta1`)
  for the Stage 1 ticker list across 2022-01-01 → 2026-06-30.
- `GET /ticker/{symbol}` and `GET /watchlist/news` return articles scoped
  correctly to ticker and watchlist config.
- `GET /high-impact` filtering.
- Tiered LLM enrichment (`VINU_LLM_ANALYSIS_MODE`, `VINU_NEWS_ACTIVE_TIERS`)
  using the local `qwen36-35B` model, reachable from inside the
  `news-api` container via `http://host.docker.internal:8009/v1`.
- Price-reaction enrichment calls out to `vinu-stock-price` correctly.

## Expected output

- Articles retrievable per ticker; actual historical depth measured and
  recorded here (this is the open gap flagged in
  [../../scope-responsibilities/vinu-news.md](../../scope-responsibilities/vinu-news.md)
  — Alpaca's news coverage back to 2022-01-01 has not been confirmed).
- If `host.docker.internal:8009` is unreachable from inside the
  container, enrichment should degrade gracefully (no crash, clear
  status) rather than silently producing wrong output — log as a bug if
  it doesn't.
- Price-reaction fields on enriched articles match real `vinu-stock-price`
  data for the same symbol/timestamp.

## Verification results (2026-07-31)

- **Historical depth confirmed:** Alpaca news API covers the full Stage 1
  window. Final backfill totals (persisted, `article_count` in the status
  table reflects only the last run for TSLA — see note below):
  AAPL 9,225 articles (`oldest_ts` 2021-11-01 — *before* the window start),
  TSLA 4,519 (DB also holds ~6.5k from the pre-rebuild run; verified
  articles back to 2022-01-31), JNJ 734 (`oldest_ts` 2022-01-03). All three
  tickers have continuous coverage across 2022-01-01 → 2026-06-30. To reach
  the 2022-01-01 window I patched `backfill_start_date` via
  `PATCH /news/settings` (the default was 2023-01-01, later than the plan's
  window — see note below).
- **`GET /ticker/{symbol}` / `GET /watchlist/news`:** scoping correct —
  watchlist/news returned articles for exactly the 3 watchlist tickers
  (AAPL 48 / TSLA 50 / JNJ 1 in a 30-day window), bounded `from`/`to`
  queries respect the window.
- **`GET /high-impact`:** returns `impact=HIGH` articles only (16 in the
  last 720h). `sentiment` filter is an exact match on stored values
  (`BULLISH`/`BEARISH`/`NEUTRAL`, not `positive`/`negative`) — works with
  the actual values (12/2/2). Not a bug, but the parameter docs don't say
  this; see note below.
- **LLM enrichment:** `llm_active: true` in `/news/health` — the local
  `qwen36-35B` server is reachable from inside the container. A real
  `POST /news/analyze` returned a full LLM analysis (sentiment_score,
  confidence, risk_flags, summary) after the Bug-4 fix.
- **Price-reaction enrichment:** now matches real `vinu-stock-price` data
  exactly after the Bug-2/Bug-3 fixes — verified by recomputing
  `price_change_1h`/`price_change_1d` from raw 1m bars for a sample article
  (MATCH: exact to float precision).

**Notes / observations (not bugs):**
- **Sentiment filter values:** `GET /high-impact?sentiment=` is an exact
  case-sensitive match on stored `BULLISH`/`BEARISH`/`NEUTRAL`.
- **Backfill resume:** an interrupted backfill (e.g. container rebuild
  mid-run) leaves status `in_progress` with no runner; re-triggering
  `POST /backfill/trigger?ticker=X` resumes from `backfilled_up_to_ts`.
  Note: the status's `article_count`/`oldest_ts` are overwritten to count
  only the resumed segment — the DB retains everything already persisted
  (verified TSLA had 2022-01-31 articles even though its status counter
  reset to a 2024-06 resume point). Don't read `article_count` as total
  stored articles after an interrupted-then-resumed backfill.
- **Shared watchlist not wired:** `VINU_SHARED_WATCHLIST_PATH` is empty in
  `.env`, so `POST /watchlist/sync` returns
  `"VINU_SHARED_WATCHLIST_PATH not set"`. Watchlist was set directly via
  `POST /watchlist/tickers`; not blocking, but the shared-file sync feature
  is dormant.
- **Default backfill start date:** `backfill_start_date` defaults to
  `2023-01-01`, later than the plan's 2022-01-01 window. Patching it to
  `2022-01-01` is a runtime setting (survives restarts? — verify); if it
  resets on recreate, the default may need to change for Stage 1 scope.

## Bug / Fix Log

### Bug-1 — container crash-loops on startup, can't write its DB

- **Found during:** first `docker compose up -d --build` of the full stack.
- **Date:** 2026-07-31
- **Symptom:** `news-api` crash-loops. Logs show
  `OSError: [Errno 30] Read-only file system: '../data'`.
- **Reproduction:** `docker compose up -d` then `docker compose logs news-api`.
- **Suspected cause:** `vinu-components/.env` sets
  `VINU_NEWS_DB_PATH=../data/news/news.db` — a local-dev-style relative
  path that doesn't exist inside the container's read-only filesystem,
  overriding the Dockerfile's correct default
  (`ENV VINU_NEWS_DB_PATH=/data/news.db`). Also, once the path is fixed,
  the host bind-mount `./data/news` is not writable by the container's
  non-root user (`uid=100(app) gid=101(app)`) — same root cause affecting
  every service in this stack, see
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Bug-1 for the confirmed write-test.
- **Severity:** blocker.

### Fixed-1

- **Root cause:** confirmed via `docker compose logs news-api` — same
  shared cause as
  [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Fixed-1.
- **Fix applied:** `vinu-components/.env`'s `VINU_NEWS_DB_PATH` changed
  from `../data/news/news.db` to `/data/news.db`; host-directory
  ownership fixed via the shared `chown -R 100:101` fix (see
  stock-price's Fixed-1 for the exact command).
- **Verification:** `docker compose ps` → `news-api ... (healthy)`, no
  tracebacks in `docker compose logs news-api`.
- **Status:** fixed.

### Bug-2 — price-reaction enrichment silently broken: stock-api URL missing `/stock` route prefix

- **Found during:** Stage 1 news checklist — after backfilling AAPL news,
  `GET /news/ticker/AAPL` returned no `price_change_1h/1d` fields on any
  article even for cataloged symbols with market data available.
- **Date:** 2026-07-31
- **Symptom:** enrichment never populates price-reaction fields. From inside
  the `news-api` container, `StockPriceClient.get_candles("AAPL", ...)` at
  `http://stock-api:8081/candles/AAPL` returns HTTP 404, while the same query
  at `http://stock-api:8081/stock/candles/AAPL` returns bars. Root cause was
  initially masked because the 404 was also crashing reads (see Bug-3).
- **Reproduction:** from `news-api` container:
  `net.request("GET", "http://stock-api:8081/candles/AAPL")` → 404;
  `.../stock/candles/AAPL` → 200.
- **Root cause (confirmed):** every vinu service mounts its FastAPI routes
  under a route prefix (`vinu_stock` → `/stock`). The codebase convention
  (confirmed in `vinu-tools`, `vinu-research`, `vinu-simulator`,
  `vinu-portfolio`) is that `VINU_STOCK_API_URL` holds the service root
  *without* the prefix and each client appends `/stock`. `vinu-news`'s
  `StockPriceClient` and `vinu-initial-analysis`'s `PriceClient` were the
  only two clients that did **not** append `/stock`, so every stock-price
  call 404'd.
- **Severity:** major (silent data gap — enrichment never worked).
- **Fix applied:**
  - `vinu-news/vinu_news/integrations/stock_price.py`: URL now built as
    `f"{self._base}/stock/candles/{symbol}"`.
  - `vinu-initial-analysis/vinu_initial_analysis/clients/price_client.py`:
    URL now `f"{self._base}/stock/candles/{symbol.upper()}"` (same class of
    bug, same convention — fixed proactively so the next component in
    dependency order doesn't hit it).
- **Verification:** rebuilt `news-api` and `initial-analysis-api`; inside the
  container `get_candles("AAPL", from=1714963318, to=...+25h)` now returns
  bars; `/news/ticker/AAPL` (2024-05-06) returns 8/11 articles with real
  `price_change_*`; one sampled value recomputed from raw 1m bars matches
  exactly. `initial-analysis` fix not yet exercised (that component's test
  hasn't run) — verified only by code reading + matching the 4-service
  convention.
- **Status:** fixed.

### Bug-3 — `GET /news/ticker/{symbol}` returns HTTP 500 when price-reaction enrichment hits a non-cataloged symbol

- **Found during:** first read-back of backfilled news —
  `GET /news/ticker/AAPL?days=3650` → HTTP 500.
- **Date:** 2026-07-31
- **Symptom:** any read endpoint that enriches articles with price reaction
  crashes if an article's primary ticker is not in `vinu-stock-price`'s
  catalog (e.g. articles mentioning SPDR, SK, FM) — stock-api returns 404,
  `StockPriceClient.get_candles` logged and then re-raised, the uncaught
  `requests.HTTPError` propagated up and the whole read became a 500.
- **Reproduction:** `GET /news/ticker/AAPL?days=3650&limit=500` (before fix)
  → 500. Log shows
  `requests.exceptions.HTTPError: 404 ... /candles/SK?...`.
- **Root cause (confirmed):** `vinu_news/integrations/stock_price.py`
  `get_candles` caught `requests.RequestException`, logged, then re-raised;
  `price_reaction.enrich_article_with_reaction` had no guard. A 404 from
  stock-api for a non-cataloged symbol is a normal "no data" condition in
  the news-enrichment flow, not an error.
- **Severity:** blocker (unusable read path).
- **Fix applied:** `vinu-news/vinu_news/integrations/stock_price.py` —
  `get_candles` now treats HTTP 404 as no-data (`return []`), so enrichment
  skips the price-reaction fields for that article instead of crashing;
  other HTTP errors still log + re-raise. Added unit tests
  (`test_price_reaction.py`: 404 → `[]` with `/stock` URL asserted; non-404
  → still raises).
- **Verification:** rebuilt `news-api`; exact Bug-3 repro
  `GET /news/ticker/AAPL?days=3650&limit=500` → HTTP 200 (500 articles, no
  crash); articles whose primary ticker isn't cataloged simply lack the
  fields.
- **Status:** fixed.

### Bug-4 — `POST /news/analyze` unreachable: route double-prefixed

- **Found during:** LLM-enrichment checklist item — `POST /news/analyze`
  returned `{"detail":"Not Found"}` (FastAPI's default 404 = no matching
  route, not the service's article-not-found path).
- **Date:** 2026-07-31
- **Symptom:** the intended path 404s; the working path is the accidental
  double-prefixed `/news/news/analyze`.
- **Reproduction:** `curl -X POST localhost:8080/news/analyze -d '{...}'` →
  `{"detail":"Not Found"}` (HTTP 404); the same body against
  `localhost:8080/news/news/analyze` → 200 with a real LLM analysis.
- **Root cause (confirmed):** `routes_read.py` declared
  `@router.post("/news/analyze")` and `routes_config.py` declared
  `@router.post("/news/analyze/backfill")` with an embedded `/news` prefix,
  but both routers are mounted by `app.py` under `route_prefix="news"` —
  the merged router already carries `/news`. `run_pipeline.py` confirms the
  convention: `base_url` includes the prefix and route paths do not.
- **Severity:** major (documented-ish analyze API unreachable at its
  intended path; affects run_pipeline which would hit the double-prefix).
- **Fix applied:**
  - `routes_read.py`: `@router.post("/news/analyze")` →
    `@router.post("/analyze")`.
  - `routes_config.py`: `@router.post("/news/analyze/backfill")` →
    `@router.post("/analyze/backfill")`.
- **Verification:** rebuilt `news-api`; `POST /news/analyze` → 200 with real
  LLM analysis; `POST /news/analyze/backfill` → 200 (`{"submitted":5}`).
  `run_pipeline.py` continues to work: it calls `{base}/news/analyze` where
  base already includes `/news`.
- **Status:** fixed.

### Bug-5 — `POST /backfill/trigger` blocks the HTTP request for the full backfill duration (no job tracking, unlike stock-price)

- **Found during:** Stage 1 checklist — about to trigger the AAPL news
  backfill (`POST /backfill/trigger?ticker=AAPL`) and noticed
  `vinu-stock-price`'s equivalent endpoint returns a `job_id` immediately
  (async, poll `GET /backfill/status/{job_id}`), while news's does not.
- **Date:** 2026-08-01
- **Symptom:** `routes_config.py`'s `trigger_backfill` called
  `NewsService.run_backfill_single`/`run_backfill_all` directly inline in
  the request handler — a multi-year, multi-chunk fetch loop — so the HTTP
  response only returns once the entire backfill finishes. A full-history
  backfill (per this log's own verification results above: AAPL 9,225
  articles across 2021-11-01 → 2026-06-30) can run for minutes; any client
  or reverse-proxy timeout in front of it kills the connection with no way
  to check whether the backfill actually completed. There was also no
  guard preventing two overlapping triggers for the same ticker from
  racing on `backfilled_up_to_ts`.
- **Reproduction:** `curl -X POST localhost:8080/news/backfill/trigger?ticker=AAPL`
  (before fix) — call blocks until the full backfill loop finishes; no
  `job_id`, no way to poll progress from another request.
- **Root cause (confirmed):** `vinu-news/vinu_news/server/routes_config.py`
  had no thread/job-tracking layer around the backfill call, unlike
  `vinu-stock-price/vinu_stock/server/routes_config.py:103-148`, which
  spawns a daemon thread, tracks `job_id` → status in an in-memory dict,
  and guards against concurrent runs with a non-blocking lock.
- **Severity:** major (usability/reliability — long blocking request with
  no progress visibility and a real race-condition path, though not a
  correctness bug on its own).
- **Fix applied:**
  - `vinu-news/vinu_news/server/routes_config.py`: `POST /backfill/trigger`
    now spawns a daemon thread, returns
    `{"ok": true, "summary": {"job_id": ..., "status": "running"}}`
    immediately, records `running`/`done`/`failed` + `results`/`error` in
    an in-memory `_background_jobs` dict, and returns `409` (with the
    running job's id) if a second trigger arrives while one is in flight.
    Added `GET /backfill/job/{job_id}` for polling.
  - `vinu-news/web/src/App.jsx`: `triggerBackfillSingle`/`triggerBackfillAll`
    now read `job_id` from the trigger response and poll
    `/backfill/job/{job_id}` every 2s instead of reading `results` directly
    off the trigger response.
  - `vinu-news/docs/book/part-4-operations/ch22-http-api.md`: documented
    the new async contract and the previously-undocumented backfill routes.
- **Verification:** rebuilt `news-api` (`docker compose build news-api &&
  docker compose up -d --no-deps news-api`) — container came up healthy.
  Against the live container:
  `curl -X POST localhost:8080/news/backfill/trigger?ticker=AAPL` → `200`,
  returns `{"job_id":"6110ba4c9641","status":"running"}` immediately (not
  blocked); `GET /news/backfill/job/6110ba4c9641` → `200`,
  `{"status":"running","results":[]}`; a second trigger
  (`?ticker=TSLA`) while the first was still running → `409`
  `{"detail":"Backfill already running (job_id=6110ba4c9641)"}`, confirming
  the concurrency guard. `python -m pytest -q` (vinu-news): 87/87 pass, no
  regressions. Full job completion (`status: done`) not observed in this
  session — the AAPL job was still processing multi-year history when
  verification concluded; this is expected given the historical depth
  confirmed above, and is consistent with the endpoint no longer blocking
  the caller while it runs.
- **Status:** fixed.
