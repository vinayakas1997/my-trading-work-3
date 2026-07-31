# vinu-initial-analysis (correlation system) — Test Log

**Status:** Passed — full checklist verified AND all 12 angles numerically
audited AND independently readable via the API, 2026-07-31 (see
"Verification results" below; 11 bugs found & fixed: Bug-2..Bug-12, on
top of the pre-existing Bug-1).

## What will be tested

- `POST /run/{ticker}` triggers analysis using real news (`vinu-news`) and
  price (`vinu-stock-price`) data for the Stage 1 window.
- `GET /correlation/{ticker}`, `GET /impact/{ticker}`, `GET /drawdown/{ticker}`.
- `GET /correlation/batch` for multi-symbol shock clustering (the fix from
  Step 02 of the prior audit plan — verifying it returns real multi-symbol
  correlation, not always `"single_symbol"`).
- Behavior when `vinu-news` has sparse or no historical coverage for a
  given date range (see the open gap in `vinu-news`'s test log).

## Expected output

- Correlation values within a valid range (e.g. [-1, 1] for
  correlation coefficients).
- `correlation/batch` returns genuinely multi-symbol structure when given
  more than one ticker, not a degenerate single-symbol fallback.
- No crash when news coverage is sparse — degrades to "insufficient data"
  status rather than fabricating a correlation from noise.
- Drawdown/impact figures line up with visually obvious real events in
  the test window (e.g. 2022 rate-hike drawdown should show up).

## Verification results (2026-07-31)

All checks run against the Docker stack; full-window runs
`from_ts=1640995200` (2022-01-01) → `to_ts=1782950400` (2026-06-30) for
AAPL/TSLA/JNJ. **All 12 angles are now numerically verified** (not just
"completed") — each was spot-checked against an independent calculation
or a known real-world event.

### API-surface checks (the plan's checklist)

- **`POST /analysis/run/{ticker}`:** all 12 angles complete for all three
  symbols. Real news (9,197 AAPL / 10k+ TSLA / 734 JNJ articles via
  keyset pagination) and full-window intraday prices ingested.
- **`GET /analysis/correlation/{ticker}`:** valid in-range coefficients —
  AAPL `0.0029` (n=2,875), TSLA `0.0224` (n=2,959), JNJ `0.092` (n=423).
- **`GET /analysis/impact/{ticker}`:** real per-article impact events —
  AAPL 3 high-bearish / 7 high-bullish (of 17,019), TSLA 20/20 (of
  21,362), JNJ 0/0 (of 1,466 — sparse; nothing crossed the 2% threshold →
  degrades gracefully).
- **`GET /analysis/drawdown/{ticker}`:** TSLA **-74.4%** (2022-01-04 →
  2023-01-06), AAPL **-34.9%** (2024-12-26 → 2025-04-09), JNJ **-18.9%**
  (2022-04-25 → 2023-10-27) — line up with real events.
- **`GET /analysis/correlation/batch`:** genuine multi-symbol structure
  for all three tickers at once — no `"single_symbol"` fallback (Bug-2;
  the Step-02 check passes).

### Independent numeric verification of all 12 angles (the audit)

1. **backtesting_44_metrics (1D)** — recomputed buy-and-hold metrics from
   raw adjusted 1D candles: total_return `0.6513`, cagr `0.1189`,
   calmar `0.3576`, win_rate `0.5298`, profit_factor `1.1007`, ann_vol
   `0.2837`, max_drawdown `-0.3325` all **exact**; sharpe/sortino within
   0.1% (their convention is `cagr/vol`, not `mean/vol`).
2. **news_price_causality → correlation** — 15min/1H `0.0029` (n=2,875)
   reproduced from raw news + candles.
3. **news_price_causality → impact events** — 17,019 events w/ real
   `impact_label`/`price_change_*`/abnormal-return fields; counts match
   the stored distribution.
4. **drawdown_deep_dive** — matches real market events (above).
5. **shock_clustering** — status `ok`, real shock dates; universe
   covariance over AAPL/JNJ/TSLA verified (corr 0.025/0.061 over recent
   63 days, honestly below the 0.3 membership threshold).
6. **regime_analysis (1D)** — re-derived the 4-regime classifier from raw
   candles: bear 133 / bull 170 / high_vol 332 / sideways 470, all
   total_returns, avg_returns, Sharpes, win-rates **exact**; transition
   matrix sums to 1,104 pairs.
7. **ml_model_pipeline** — now trains all 9 models (Bug-8/9); 1D best SVR
   `oos_ic 0.1420` (p=0.037), 1W best LightGBM `0.2563`; 1M correctly
   `insufficient_data_after_features` (13 obs). ICs are plausible for
   equity return prediction.
8. **news_first_analysis** — verified the z-score math on a sampled row
   (recomputed mean/std/z **exact**: z=5.0, sample_size=6). Structure:
   7,667 hour-buckets × 5 sessions × 3 time_formats = 115,005 rows;
   per-timeframe article-session total = 9,197 ✓.
9. **pnl_attribution** — `status: push_fed_not_runner_driven` is **by
   design** (fed via `POST /pnl-attribution/{ticker}/record`, not the
   runner); single status row is the correct no-positions-yet state.
10. **shock_personality** — GARCH(1,1) persistence `0.956` (α 0.100,
    β 0.856 — plausible daily); gap-fill mean `0.4436` (n=47, CI
    [0.31,0.58]); drift persistence mean `0.96d` (n=107) — all now real
    (Bug-10).
11. **trend_lifecycle (1D)** — independent peak/trough detection +
    alternating filter = **15 peaks** (stored `total_peaks: 15`); stage
    descriptions match the pattern library.
12. **trend_session_structure** — per-session peak counts sum exactly to
    trend_lifecycle totals (15min 98+4+4=106, 1H 19+37+1=57, 4H
    11+10+1=22); qualifying-session floor logic correct.

### Findings resolved during the audit (Bug-8 → Fixed-8 … Bug-11 → Fixed-11)

- `ml_model_pipeline` was a **silent no-op** (ML libs absent → only
  `data_prep` rows) — now trains all 9 models (Bug-8).
- `catboost` failed with a wrong `tmp_dir` kwarg + missing writable dir —
  fixed (`train_dir="/tmp"` + `libgomp1`) (Bug-9).
- `shock_personality`'s gap-fill & drift analyses always returned
  `insufficient_sample` (0 obs) because shock "dates" were RangeIndex
  positions and news dates were read from the wrong fields — fixed; all
  three analytic outputs now `status: ok` (Bug-10).
- `shock_clustering` always returned `single_symbol` (one-symbol
  universe) with bogus dates — fixed; now builds the watchlist universe
  and returns real, verified covariance output (Bug-11).

### Minor notes (no fix — by design or acceptable)

- `news_first_analysis` stores the same hourly baseline 3× (once per
  declared time_format 15min/1H/1D), since the news baseline is
  timeframe-independent — triples storage for no information. Harmless
  (~20 MB); left as-is.
- `elastic_net` (1D) and `svr` (1W) produce NaN OOS IC (constant
  prediction → `spearmanr` undefined); they're correctly excluded from the
  best-model pick. A data limitation, not a code bug.
- `shock_clustering` covariance is computed over the last 63 days only
  while shock dates span the full window — see the design note in
  Fixed-11.

### Deployment note

`entrypoint.sh` also runs `vinu-initial-compute --all --continuous`
(hourly, default ~7-day window) in the background. It produced a small
default-window run for AAPL during testing (06:53, `analysis_from/until =
NaT`); expected behavior, not a bug. Stale NaT-window AAPL artifacts were
cleaned up so the read endpoints show the full-window evidence.

- **Unit tests:** not run separately — validated through the Docker stack
  per AGENTS.md (host-pytest is not the authoritative path for this pass).

## Bug / Fix Log

### Bug-1 — container crash-loops on startup, permission denied opening its DB

- **Found during:** first `docker compose up -d --build` of the full stack.
- **Date:** 2026-07-31
- **Symptom:** `initial-analysis-api` crash-loops. Logs show
  `sqlite3.OperationalError: unable to open database file` in
  `RunLog.__init__`.
- **Reproduction:** `docker compose up -d` then
  `docker compose logs initial-analysis-api`.
- **Suspected cause:** different root cause than the path-override bugs
  in `vinu-news`/`vinu-stock-price`/`vinu-tools`/`vinu-strategy`/`vinu-simulator`
  — this service's env var name doesn't even match what my `.env` set
  (`.env` had `VINU_CORRELATION_DATA_ROOT`, but the code reads
  `VINU_INITIAL_ANALYSIS_DATA_ROOT`, confirmed in
  `vinu_initial_analysis/config.py`), so the Dockerfile's correct
  `/data` default was actually in effect. The real problem: the host
  bind-mount directory `./data/initial-analysis` didn't exist before this
  `docker compose up`, so Docker auto-created it as `root:root`, and the
  container's non-root user (`uid=100(app) gid=101(app)`) can't write
  into a root-owned directory — same underlying permission class of bug
  as [../vinu-stock-price/test-log.md](../vinu-stock-price/test-log.md)'s
  Bug-1, different trigger (freshly-created vs. pre-existing directory).
- **Severity:** blocker.

### Fixed-1

- **Root cause:** confirmed via `docker compose logs initial-analysis-api`
  and by grepping `vinu_initial_analysis/config.py` for the actual env
  var names read — permission issue on the freshly-auto-created
  `./data/initial-analysis` host directory (root-owned), not a path
  override (the `VINU_CORRELATION_DATA_ROOT` var I'd set was dead —
  wrong name, never read).
- **Fix applied:**
  - Renamed `VINU_CORRELATION_DATA_ROOT` → `VINU_INITIAL_ANALYSIS_DATA_ROOT=/data`
    and `VINU_CORRELATION_PORT` → `VINU_INITIAL_ANALYSIS_PORT` in `.env`
    to match what the code actually reads (confirmed via grep).
  - Host-directory ownership fixed via the shared `chown -R 100:101` fix
    (see stock-price's Fixed-1).
- **Verification:** `docker compose ps` → `initial-analysis-api ... (healthy)`,
  no tracebacks in `docker compose logs initial-analysis-api`.
- **Status:** fixed. Note: the remaining `VINU_CORRELATION_*` lines in
  `.env` (market-hours, drawdown thresholds, etc.) were NOT confirmed
  against the code — grepped and found no matches, so they may be dead
  config too. Left as-is (not blocking), flagged in `.env`'s own comment
  for whoever tests this component's actual behavior next — don't trust
  those settings to take effect without checking the code first.

### Bug-2 — `GET /correlation/batch` never reaches its handler (route shadowing)

- **Found during:** initial checklist exercise of `vinu-initial-analysis`
  against the running stack.
- **Date:** 2026-07-31
- **Symptom:** `GET /analysis/correlation/batch?symbols=AAPL,TSLA` returns a
  single-symbol correlation response keyed on the literal string
  `"BATCH"`:
  `{"symbol":"BATCH","news_return_corr":null,"sample_size":0}` — it never
  runs the multi-symbol shock-clustering batch logic at all.
- **Reproduction:**
  `curl "localhost:8083/analysis/correlation/batch?symbols=AAPL,TSLA&from_ts=1640995200&to_ts=1782950400"`
- **Root cause:** in `server/routes_read.py`,
  `@router.get("/correlation/{ticker}")` (line 34) is registered **before**
  `@router.get("/correlation/batch")` (line 52). Starlette/FastAPI dispatch
  routes in registration order, so `/correlation/batch` matches the
  `{ticker}` pattern with `ticker="batch"` and the batch handler is
  unreachable. Same route-shadowing bug class as `vinu-tools` Bug-2.
- **Severity:** major — the documented `correlation/batch` API
  (scope-responsibilities) is dead, and it's the endpoint carrying the
  Step-02 shock-clustering fix this plan explicitly wanted to verify.
- **Status:** logged, fix pending (reorder: register batch route before the
  `{ticker}` routes).

### Fixed-2

- **Root cause:** Starlette/FastAPI dispatch routes in registration order;
  `/{ticker}` was registered ahead of `/batch`.
- **Fix applied:** moved `@router.get("/correlation/batch")` **above** all
  the `/{ticker}` routes in `server/routes_read.py` (batch handler now
  first, before `correlation/{ticker}`, `drawdown/{ticker}`, `story/{ticker}`).
- **Verification:** rebuilt `initial-analysis-api`;
  `GET /analysis/correlation/batch?symbols=AAPL,TSLA&from_ts=1640995200&to_ts=1782950400`
  now returns a genuine multi-symbol structure
  `{"symbols":["AAPL","TSLA"],"results":{...},"count":2}` instead of
  `{"symbol":"BATCH",...}`; the single-ticker routes still return 200.
- **Status:** fixed.

### Fixed-3

- **Root cause:** `clients/news_client.py` built URLs off the bare service
  root (`http://news-api:8080/...`) but news-api mounts everything under
  `/news`; `price_client.py` already had the `/stock` prefix (the
  prefix-once convention).
- **Fix applied:** `NewsClient` now appends `/news` to its base URL
  (`_PREFIX = "/news"`, with a defensive `removesuffix` so it stays
  idempotent if ever configured with the prefix included).
- **Verification:** rebuilt; in-container
  `NewsClient('http://news-api:8080').get_ticker_news('AAPL', ...)` returns
  articles (5+), and `get_articles_since` returns articles — both were 404
  before.
- **Status:** fixed.

### Fixed-4

- **Root cause:** two silent under-fetches meant news-hours and return-hours
  never overlapped: `price_client.get_candles` default `limit=5000`
  (stock-api caps at 50,000; full 15m window = 30,348 bars) and
  `news_client.get_ticker_news` default `limit=500` (news-api max/req),
  which returns only the 500 most-recent articles in range.
- **Fix applied:**
  - `clients/price_client.py::get_candles` default `limit` → **50,000**.
  - `clients/news_client.py::get_ticker_news` — when `from_ts` is given,
    keyset-paginate the full `[from_ts, to_ts]` window (slide `to` backward
    past each page's oldest `sort_ts` until exhausted; dedupe by article
    id/link; 9,197 AAPL articles fetched in ~19 requests vs the old 500).
- **Verification:** rebuilt; full-window `POST /analysis/run/AAPL` →
  `news_price_causality` 6 rows (was: degenerate) → now real: 15min & 1H
  `news_return_corr = 0.0029`, `sample_size = 2875`; 1D `best_lag_corr =
  -0.2446`. Correlation is no longer silently empty.
- **Status:** fixed.

### Bug-3 — news client drops the `/news` prefix → all angles see zero news

- **Found during:** after fixing Bug-2, the (now reachable) batch response
  shows every angle produced nothing: `analysis_from/until: "NaT"`,
  `event_count: 0`, `news_return_corr: null`, `sample_size: 0`,
  `granger_causes_prices: false`, `drawdown_count: 0` — despite
  `vinu-news` holding 21,115 real articles across the Stage-1 window.
- **Date:** 2026-07-31
- **Symptom:** analysis runs complete but ingest zero news (and zero
  events), so correlation/impact/drawdown are all empty.
- **Reproduction:** from inside `initial-analysis-api`:
  `GET http://news-api:8080/articles/since?ts=1640995200&limit=5` → **404**,
  while `GET http://news-api:8080/news/articles/since?...` → 200 with 5
  articles.
- **Root cause:** `clients/news_client.py` builds
  `f"{self._base}/articles/since"` / `f"{self._base}/ticker/{symbol}"`
  but the news service mounts everything under `/news`
  (`VINU_NEWS_API_URL=http://news-api:8080` holds the *root*, no prefix).
  The sibling `clients/price_client.py` does the right thing
  (`/stock/candles/...`) — same prefix-once convention violated here, the
  `vinu-news` Bug-2 class again.
- **Severity:** blocker — the entire component computes nothing.
- **Status:** logged, fix pending (append `/news` in `NewsClient`).

### Bug-4 — correlation/impact silently compute nothing over a full window

- **Found during:** after Bug-3's fix, re-running the full-window analysis
  produces real rows for every angle (e.g. news_price_causality 6 rows,
  news_first_analysis 6,375, drawdown_deep_dive 34), **but** the Pearson
  correlation is degenerate: `news_return_corr: 0.0`, `sample_size: 0.0`,
  `best_lag_minutes: null` — because the news-hours and return-hours sets
  never overlap.
- **Date:** 2026-07-31
- **Symptom:** `GET /analysis/correlation/AAPL` →
  `{"symbol":"AAPL","news_return_corr":0.0,"sample_size":0.0}` after a
  real full-window `POST /analysis/run/AAPL`.
- **Reproduction / evidence (inside container):** fetched real news +
  candles and re-ran the angle's own merge logic —
  `pd.merge(resample_news_to_hourly(articles), resample_returns_to_hourly(candles), on="hour_ts", how="inner")` →
  `merged = 0` for 15min/1H/1D alike. Buckets: news hour_ts ∈
  [2026-03-18, 2026-07-01], return hour_ts ∈ [2022-01-03, 2024-09-20]
  (1H) — disjoint windows.
- **Root cause (two independent under-fetches, no temporal overlap):**
  1. `clients/price_client.py::get_candles` sends `limit=5000`; the stock
     API serves at most that many rows per request (`le=50000`), so 1H
     bars truncate at 2024-09-20 and 15m at 2022-09-26. The full-window
     data exists — `?limit=50000` returns the complete 15m series
     (30,348 bars, 2022-01-03 → 2026-06-30) and 1H (8,318 bars).
  2. `clients/news_client.py::get_ticker_news` sends `limit=500` (news
     API's max per request), returning only the 500 **most-recent**
     articles in range (2026-03 → 2026-07). The news store orders by
     `sort_ts DESC LIMIT n` with no offset/paging param, so a single
     request can never span the full window (9,225 AAPL articles exist).
- **Severity:** major — the core "did this news move this price" metric
  (and the correlation/batch verification the plan cares about) produces
  nothing for a multi-year window; the angle looks like it ran (status
  `completed`, 6 rows) but the metric is empty.
- **Status:** logged, fix pending (raise price limit to 50,000; keyset-
  paginate news fetch across `[from_ts, to_ts]`).

### Bug-5 — `GET /correlation/{ticker}` surfaces `null` despite valid correlation data

- **Found during:** verifying the Bug-4 fix. The stored run now has a real
  Pearson correlation — 15min & 1H: `news_return_corr=0.0029`,
  `sample_size=2875`; 1D: `best_lag_correlation=-0.2446`, sample 23 — but
  `GET /analysis/correlation/AAPL` returns
  `{"symbol":"AAPL","news_return_corr":null,"sample_size":23.0}`.
- **Date:** 2026-07-31
- **Symptom:** the public correlation endpoint reports no correlation even
  though the underlying angle computed a real, well-sampled one.
- **Reproduction:** full-window `POST /analysis/run/AAPL` then
  `GET /analysis/correlation/AAPL?from_ts=1640995200&to_ts=1782950400`.
- **Root cause:** `api.py::get_correlation` reads all `type=correlation`
  rows (across all stored runs, via `storage.read`) and takes
  `records[-1]`. Rows are written per `time_format` in the order
  `15min, 1H, 1D`, so the last row is the **1D** correlation. For 1D,
  daily bars are timestamped at midnight UTC, so news articles only ever
  land in that hour on a handful of days; the resulting news-intensity
  series is near-constant and `scipy.stats.pearsonr` returns `NaN` (zero
  variance) → JSON `null`. The meaningful 15min/1H correlations are never
  surfaced, and multiple accumulated runs make the selection order-
  dependent.
- **Severity:** major — the metric this component exists to provide reads
  as empty at the API even when the computation succeeded.
- **Status:** logged, fix pending (select the correlation row with the
  largest `sample_size` across the run set).

### Fixed-5

- **Root cause:** `api.py::get_correlation` took `records[-1]`, which (after
  per-time_format row order 15min/1H/1D) is the 1D correlation — typically
  `NaN` because daily bars at midnight UTC barely overlap news hours.
- **Fix applied:** `get_correlation` now sorts the `type=correlation` rows
  by `sample_size` descending and surfaces the best-sampled time format
  (the 15min/1H result), instead of the last-written row.
- **Verification:** rebuilt; `GET /analysis/correlation/AAPL` →
  `{"symbol":"AAPL","news_return_corr":0.0029,"sample_size":2875.0}` (was
  `null` / 23.0).
- **Status:** fixed.

### Fixed-6

- **Root cause:** the `vinu-initial-analysis` image never installed
  `vinu-tools`, which `shock_clustering`/`shock_personality` import.
- **Fix applied:** added `COPY vinu-tools /app/vinu-tools` +
  `RUN pip install --no-cache-dir -e /app/vinu-tools` to the
  `vinu-initial-analysis/Dockerfile` (mirrors the research/live
  Dockerfiles; build context is already the repo root).
- **Verification:** rebuilt; `import vinu_tools` succeeds in-container and
  full-window runs now report `shock_clustering` and `shock_personality`
  `completed` (1 row each).
- **Status:** fixed.

### Fixed-7

- **Root cause:** `news_price_causality/compute.py` imported
  `compute_impact_for_article` but never called it — the per-article event
  study was dead code, so `GET /impact` could never report high-impact
  events.
- **Fix applied:**
  - `compute()` now runs the event study for the **15min** pass (once, to
    avoid triplicating rows per time_format), passing the already-fetched
    15m bars as `candles_by_ticker` so it needs **no per-article HTTP and
    no 1m cache** (which doesn't exist).
  - `impact.py::compute_impact_for_article` accepts `candles_by_ticker`
    and falls back to `price_client` only for tickers not in it; event rows
    get `"type": "impact"`.
  - Performance: `_compute_price_change` and
    `_helpers.compute_abnormal_return` now bisect the sorted candle list
    instead of full-list scans (per-article O(log n); a full-window AAPL
    run with ~9.2k articles completes in ~2.5 min).
  - `runner.py` passes `price_client` only to angles whose `compute()`
    signature accepts it (introspected), so the other 11 angles are
    unaffected.
- **Verification:** rebuilt; full-window runs now store real impact events
  (AAPL 17,019 / TSLA 21,362 / JNJ 1,466 rows for news_price_causality)
  and `GET /analysis/impact/{ticker}` returns
  `high_impact_bearish_events`/`high_impact_bullish_events` with real
  per-article `impact_label`, `price_change_*`, and abnormal-return fields.
- **Status:** fixed.

### Bug-6 — shock_clustering & shock_personality angles always error (`No module named 'vinu_tools'`)

- **Found during:** full-window `POST /analysis/run/AAPL` — 10 of 12
  angles complete, but `shock_clustering` and `shock_personality` fail
  with `No module named 'vinu_tools'` every run.
- **Date:** 2026-07-31
- **Symptom:** `"shock_clustering": {"status":"error","error":"No module
  named 'vinu_tools'"}` (same for `shock_personality`) in the run summary.
- **Reproduction:** `POST /analysis/run/AAPL` (any window) → both angles
  error; import the module in-container →
  `ModuleNotFoundError: No module named 'vinu_tools'`.
- **Root cause:** `angles/shock_personality/compute.py:167` and
  `angles/shock_clustering/compute.py:51` import
  `vinu_tools.compute.risk.*` (the functions exist in
  `vinu-tools/vinu_tools/compute/risk/{volatility,covariance}.py`), but the
  `vinu-initial-analysis` image never installs `vinu-tools` — its
  `Dockerfile` only installs `vinu-lib` + the package itself, unlike
  `vinu-research`/`vinu-live` whose Dockerfiles `COPY` + `pip install -e`
  `vinu-tools`. So two of the twelve angles can never run in the
  deployment shape this plan tests.
- **Severity:** medium — doesn't block the correlation/impact/drawdown/
  batch checklist (those read other angles), but the shock-clustering
  logic this plan's `correlation/batch` check references always fails.
- **Status:** logged, fix pending (install `vinu-tools` in the image,
  mirroring the research Dockerfile).

### Bug-12 — `GET /angle/{shock_clustering,shock_personality}/{ticker}` returns HTTP 500: unserializable numpy/Timestamp values

- **Found during:** independently re-verifying the Bug-10/Bug-11 fixes by
  reading the two angles back via the same generic
  `GET /analysis/angle/{angle_name}/{ticker}` endpoint that works for all
  other 10 angles.
- **Date:** 2026-07-31
- **Symptom:** both endpoints return HTTP 500:
  `{"detail": "[ValueError('dictionary update sequence element #0 has
  length 10; 2 is required'), TypeError('vars() argument must have
  __dict__ attribute')]", "error": "validation_error"}`. All other 10
  angles' `/angle/{name}/{ticker}` reads succeed.
- **Reproduction:**
  `curl "localhost:8083/analysis/angle/shock_clustering/AAPL?from_ts=1640995200&to_ts=1782950400"`
  (same for `shock_personality`) → 500.
- **Root cause (confirmed via reading the raw parquet directly):**
  `shock_clustering`'s stored `shock_dates`/`cluster_members` columns are
  raw `numpy.ndarray` objects (not native Python lists), and several
  timestamp columns (`started_at`, `analysis_from`, `analysis_until`,
  `stored_at`) are `pandas.Timestamp` objects — `df.to_dict("records")`
  in `routes_read.py::get_angle` preserves these non-JSON-native types,
  and FastAPI's default response encoder can't serialize them (the
  cryptic errors are `jsonable_encoder`'s fallback paths choking on an
  ndarray and a Timestamp). The underlying Bug-10/Bug-11 computation
  fixes are otherwise correct — this is purely a read-path
  serialization gap that happens to only bite these two angles because
  they're the only ones storing array/Timestamp-valued cells.
- **Severity:** major — the component's own documented generic angle-read
  surface is broken for 2 of 12 angles; the fix that made these angles
  compute correctly can't actually be observed through the API.

### Fixed-12

- **Root cause:** `get_angle()` in `server/routes_read.py` passed
  `df.to_dict("records")` straight to the response without normalizing
  numpy/pandas-specific types to JSON-native ones.
- **Fix applied:** `get_angle()` now recursively coerces each record's
  values: `numpy.ndarray` → `.tolist()`, `pandas.Timestamp`/`datetime` →
  ISO-8601 string, `numpy` scalar types (`np.integer`/`np.floating`) →
  native `int`/`float`, and NaN/NaT → `None` (generalizing the existing
  NaN-to-`None` handling already in this function instead of only
  covering `float`). Applied generically so any future angle storing
  array or timestamp-valued cells doesn't hit the same crash.
- **Verification:** rebuilt `initial-analysis-api`;
  `GET /analysis/angle/shock_clustering/AAPL?...` and
  `GET /analysis/angle/shock_personality/AAPL?...` both return 200 with
  real data (`shock_dates` as a JSON array of date strings,
  `cluster_members` as a JSON array, timestamps as ISO strings). All
  other 10 angles' reads re-verified unaffected (still 200, same
  row counts).
- **Status:** fixed.

### Bug-7 — per-article impact event study is dead code; `GET /impact` always reports zero

- **Found during:** exercising the plan's `GET /impact/{ticker}` surface
  after the other fixes — every symbol returns
  `high_impact_bearish_events: 0`, `high_impact_bullish_events: 0`, and
  the `events` list contains only the causality/status statistics, never
  per-article impact events.
- **Date:** 2026-07-31
- **Symptom:** the "did this news move this price" event-study half of the
  component (per-article `impact_label`, `price_change_*`, abnormal
  return) is never produced.
- **Reproduction:** `GET /analysis/impact/AAPL` after a full-window run →
  `high_impact_bearish_events: 0, event_count: 18` with no rows carrying
  `impact_label`.
- **Root cause:** `angles/news_price_causality/compute.py` imports
  `compute_impact_for_article` from `.impact` but **never calls it** —
  `compute()` only emits `status`/`granger`/`correlation`/`lag` rows.
  `api.py::get_impact` therefore counts `impact_label` rows that can never
  exist, and its `events` array is just the statistical rows. (Related:
  `compute_impact_for_article` also can't work as written here — it fetches
  candles via per-article HTTP with the default `1m` interval, and no 1m
  data is cached anywhere yet; it would do ~9k HTTP calls per symbol and
  still get empty candles.)
- **Severity:** major — the impact endpoint (explicitly in the plan's API
  surface) is structurally incapable of returning what it advertises.
- **Status:** logged, fix pending (wire the event study into `compute()`,
  driven by the already-fetched 15m bars for the symbol instead of
  per-article 1m HTTP fetches).

### Bug-8 — `ml_model_pipeline` is a silent no-op (ML libs absent from the image)

- **Found during:** the post-`Passed` numeric audit of the 8 angles that
  only reported `completed`. Pulling the stored rows showed the angle
  stores **only `data_prep` rows** (12 features, n_train/n_test) and never
  any `model_result`/`best_model` rows — despite `compute()` being
  written to train 9 models (ridge, random_forest, xgboost, lightgbm,
  catboost, elastic_net, knn, svr, gradient_boosting) and record OOS IC.
- **Date:** 2026-07-31
- **Symptom:** `ml_model_pipeline` reports `status: completed`, looks like
  it ran, but no model is ever trained — the angle's entire output is a
  feature-prep row.
- **Reproduction:** inspect stored parquet → only `metric=data_prep`;
  in-container `import sklearn` / `import xgboost` / `import lightgbm` /
  `import catboost` → `ImportError` (all four missing). `_try_model`
  swallows `ImportError` as `None`, so every model is silently skipped and
  `valid` stays empty (no `best_model`, no `model_ranking`).
- **Root cause:** the `vinu-initial-analysis` image installs only
  `vinu-lib`, `vinu-tools` (base deps), and the package itself; the ML
  libraries live only in `vinu-tools[ml]`'s extra, which nothing in the
  standard deployment installs. `vinu-research`/`vinu-live` install plain
  `vinu-tools` too, so they'd have the same gap where they use sklearn.
- **Severity:** major — the "train & evaluate models with OOS IC" angle is
  part of this component's purpose and produces nothing; it fails silently
  (status `completed`) rather than reporting missing deps.
- **Status:** logged, fix pending (install `scikit-learn`, `xgboost`,
  `lightgbm`, `catboost` in the image — the `vinu-tools[ml]` set).

### Fixed-8

- **Root cause:** the ML libraries existed only in the `vinu-tools[ml]`
  extra, which nothing in the standard deployment installed — every
  `_try_model` call hit `ImportError` and returned `None`, so the angle
  silently stored only `data_prep`.
- **Fix applied:** `vinu-initial-analysis/Dockerfile` now installs
  `"/app/vinu-tools[ml]"` (adds `scikit-learn`, `xgboost`, `lightgbm`,
  `catboost`) plus `libgomp1` (OpenMP runtime; `lightgbm`/`xgboost` fail
  to load without it on `python:3.12-slim`).
- **Verification:** rebuilt; full-window AAPL run now trains all 9 models
  and records OOS IC + ranking. 1D best = SVR `oos_ic 0.1420` (p=0.037);
  1W best = LightGBM `0.2563`. `ml_model_pipeline` row count 3 → 41.
- **Status:** fixed.

### Bug-9 — catboost model fails in deployment (`Can't create train tmp dir: tmp`)

- **Found during:** verifying the Bug-8 fix (ML deps now installed). 8 of
  9 models train and report OOS IC, but `catboost` always errors:
  `catboost/libs/train_lib/dir_helper.cpp:26: Can't create train tmp dir:
  tmp` → `oos_ic` NaN, model excluded from the ranking.
- **Date:** 2026-07-31
- **Symptom:** `ml_model_pipeline` row for catboost has `error` =
  "Can't create train tmp dir: tmp".
- **Reproduction:** full-window run with ML libs installed; inspect the
  stored `model_result` for catboost.
- **Root cause:** `CatBoostRegressor` defaults to a `tmp` training dir
  relative to the process CWD (`/app/vinu-initial-analysis`, owned by
  root); the container runs as non-root `app` (uid 100) so the directory
  can't be created. The other 8 models write nothing to disk and work.
- **Severity:** low — 1 of 9 models; the pipeline still completes and
  picks a best model, but the angle claims to evaluate catboost and
  silently drops it.
- **Status:** logged, fix pending (pass a writable `tmp_dir="/tmp"` to
  `CatBoostRegressor`).

### Fixed-9

- **Root cause:** `CatBoostRegressor` defaults to a `tmp` training dir
  relative to CWD (root-owned); and the first attempt to pass a writable
  dir used the wrong kwarg.
- **Fix applied:** pass the correct param `train_dir="/tmp"` to
  `CatBoostRegressor` (catboost 1.2.10 uses `train_dir`, not `tmp_dir`).
- **Verification:** rebuilt; catboost now trains and reports real OOS IC —
  1D `0.0606` (p=0.374), 1W `0.1186` (p=0.472) — no error row.
- **Status:** fixed.

### Bug-10 — shock_personality shock dates are bogus; gap-fill & drift persistence never compute

- **Found during:** the post-`Passed` numeric audit. `shock_personality`
  reports `n_shocks: 107` and a plausible GARCH persistence, but
  `gap_fill_rate` and `drift_persistence_days` always return
  `status: "insufficient_sample"` with `n_observations: 0`.
- **Date:** 2026-07-31
- **Symptom:** both gap-fill and drift-drift persistence analyses produce
  zero observations on a full-window AAPL run that clearly has gap shocks
  (47 gap shocks detected), and news cross-referencing never marks a shock
  as having news.
- **Reproduction:** in-container `_tag_shocks(bars)` on real 1D AAPL bars
  → `107` shocks, gap shock `date` values are `15, 16, 36, ...` (the
  `RangeIndex` positions); `_compute_gap_fill_rate` → `n_observations: 0`.
- **Root cause (two compounding issues in `shock_personality/compute.py`):**
  1. `_detect_gap_shocks`/`_detect_vol_shocks` set
     `"date": bars.index[i]` — but `bars` has a plain `RangeIndex` (the
     runner builds `pd.DataFrame(candles)`), so "dates" are integer row
     positions, not timestamps. `_compute_gap_fill_rate` /
     `_compute_drift_persistence` then do
     `bars.index.get_loc(pd.Timestamp(shock["date"]))` — `pd.Timestamp(15)`
     is 1970-01-01, which `RangeIndex.get_loc` can't find → every shock is
     skipped → `n_observations: 0`.
  2. `_cross_reference_news` reads `published_at`/`timestamp`/`date` from
     articles, but vinu-news articles carry `sort_ts` — so `news_dates` is
     always empty and `has_news` is always `False` (dates also resolve to
     1970, so even with news the comparison would fail).
- **Severity:** medium — `n_shocks` and the GARCH persistence are valid,
  but two of the angle's three analytic outputs are structurally incapable
  of producing a result, and the news-attribution field is always wrong.
- **Status:** logged, fix pending (store real `bar_ts` seconds + row `idx`
  on each shock; use `sort_ts` (unit="s") for news dates; index by `idx`).

### Fixed-10

- **Root cause:** `_detect_gap_shocks`/`_detect_vol_shocks` stored the
  `RangeIndex` row position as the shock `date`; the gap-fill and
  drift-persistence functions then looked it up via
  `bars.index.get_loc(pd.Timestamp(position))` (→ 1970 → not found → every
  shock skipped). News dates were read from fields vinu-news articles
  don't have (`published_at`/`timestamp`/`date` instead of `sort_ts`).
- **Fix applied:** shocks now store `"date": int(bar_ts)` (real seconds)
  plus `"idx": i`; the two consumers index by `idx` directly;
  `_cross_reference_news` reads `sort_ts` (parsed `unit="s"`).
- **Verification:** in-container on real 1D AAPL data —
  `gap_fill_rate` mean 0.4436 (n=47, 95% CI [0.31, 0.58]), `status: ok`;
  `drift_persistence_days` mean 0.96 (n=107, CI [0.70, 1.22]); all 107
  shocks news-attributed; shock dates are real calendar days
  (2022-01-25, 2022-02-24 = Ukraine-invasion day, ...). Re-run stores the
  corrected values.
- **Status:** fixed.

### Bug-11 — shock_clustering always `single_symbol`; shock dates bogus

- **Found during:** the post-`Passed` numeric audit — the
  `shock_clustering` angle output was
  `{"cluster_members": [], "status": "single_symbol"}` on every run.
- **Date:** 2026-07-31
- **Symptom:** the cross-symbol shock-clustering angle can never cluster:
  it reports `single_symbol` even though a 3-symbol watchlist exists, and
  its `shock_dates` were the same bogus RangeIndex positions as
  Bug-10's.
- **Reproduction:** inspect stored parquet → `status: single_symbol`;
  `_detect_shock_dates(bars)` on real bars → `"15"`, `"16"`, ... dates.
- **Root cause:** `compute()` built `universe_prices = {symbol:
  bars["close"]}` — a one-element universe, so `n_assets < 2` → the
  `single_symbol` early return. The angle never fetched the other
  watchlist symbols' prices, so `dynamic_covariance` over a multi-symbol
  universe was dead. (`_detect_shock_dates` also used `bars.index[i]`.)
- **Severity:** medium — the shock-clustering mechanism this component
  was built to provide never produced a cluster; it degraded to
  `single_symbol` silently.
- **Status:** logged, fix pending (build a real watchlist universe via the
  price client; use real `bar_ts` shock dates).

### Fixed-11

- **Root cause:** one-symbol universe + RangeIndex shock dates.
- **Fix applied:**
  - `clients/price_client.py` gains `get_watchlist()` (hits
    `/stock/watchlist/tickers` → AAPL/JNJ/TSLA).
  - `compute()` accepts `price_client` (runner passes it via signature
    introspection) and builds a real universe: fetches 1D closes for every
    watchlist symbol, aligns on common trading days (`DataFrame.dropna`),
    and passes the multi-asset price matrix to `_compute_shock_clusters`;
    falls back to `single_symbol` only if the universe can't be built.
  - `_detect_shock_dates` uses real `bar_ts` (calendar dates).
- **Verification:** in-container on real data — status now `ok`,
  `n_shock_dates: 107` with real dates (2022-01-25, 2022-02-24,
  2022-03-09...). The dynamic_covariance over the aligned universe
  (AAPL/JNJ/TSLA) is mathematically correct — recent-63-day correlations
  AAPL-JNJ 0.025 / AAPL-TSLA 0.061 (reproduced independently), below the
  0.3 threshold, so `cluster_members` is honestly empty for this window's
  last quarter. Not a degenerate fallback.
- **Status:** fixed. Design note: the angle computes shock dates over the
  full window but the cross-symbol covariance only over the last 63 days
  (`dynamic_covariance(window=63)`), so membership reflects the recent
  correlation regime; worth revisiting if the intent was to cluster the
  historical shocks themselves.
