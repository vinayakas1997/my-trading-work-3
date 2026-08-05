# vinu-components Pipeline — Full Inefficiency Audit & Fix Plan

> **Audit scope:** `vinu-stock-price` → `vinu-news` → `vinu-tools` → `vinu-initial-analysis` → `vinu-strategy` → `vinu-simulator` → `vinu-research` + shared `vinu-infra`
>
> **Date:** 2026-07-21
>
> **Total findings:** 38 (6 first-pass + 32 deep-audit)

---

## How to Read

Each finding is tagged with:

| Tag | Meaning |
|-----|---------|
| 🔴 **CRITICAL** | Data loss, silent corruption, or unrecoverable failure |
| 🟠 **HIGH** | Significant waste (minutes, money) or wrong results |
| 🟡 **MEDIUM** | Noticeable waste but non-blocking |
| 🔵 **LOW** | Minor cleanup / nice-to-have |
| ⚪ **NEGLIGIBLE** | Cosmetic |

---

# First-Pass Findings (Original 6)

These were identified during the initial pipeline review. They're included here for completeness alongside the deeper audit.

---

## FP-1 🔴 Backfill Triggers ALL Symbols (Not Just Requested Ticker)

**Component:** `vinu-stock-price`
**Files:** `run_pipeline.py:268-282`, `service.py:147`, `orchestrator.py:119-157`

**Problem:**
`step_stock_price` adds only the requested ticker to the watchlist, then calls `/backfill/trigger` which runs `get_service().run_backfill()` with **no arguments** → `syms = symbols or self.get_watchlist()`. This backfills **every symbol** in the existing watchlist (14+ symbols × 4 years each), not just the requested one.

**Impact:** Every pipeline run spends ~75-83 seconds re-backfilling all watchlist symbols when only 1 ticker is needed.

**Fix Plan:**
1. Add an optional `ticker` query parameter to `POST /backfill/trigger` in `routes_config.py`
2. Pass it through `service.run_backfill(symbols=[ticker])` to `orchestrator.py`
3. In `run_pipeline.py`, call `POST /backfill/trigger?ticker=AAPL` instead of the bare endpoint
4. Also add a completeness check at the top of `_backfill_symbol` in `orchestrator.py:78`:
   ```python
   entry = catalog.get_symbol(sym)
   if entry and entry.backfill_status == "complete":
       return  # skip already-complete symbols
   ```

---

## FP-2 🟠 Research Ignores Prior Simulation Results

**Component:** `vinu-research`
**Files:** `service.py:57-179`, `loop.py:191-355`, `routes_read.py:42-59`

**Problem:**
The pipeline runs the simulator first, generating a working strategy. Then `step_research` calls `/research/run` which creates a fresh `StrategyResearchLoop` and runs the full LLM-based strategy generation from scratch. It never checks whether the simulator already produced results for this symbol.

**Impact:** 6-7 LLM calls (~4 minutes, ~40s each) wasted regenerating what the simulator already computed.

**Fix Plan:**
1. Add a `strategy_code` field to `RunResearchRequest` Pydantic model in `routes_read.py`
2. In `service.run_research()`, if `strategy_code` is provided, skip LLM generation and go straight to backtest + critic
3. In `loop.run()`, accept optional `initial_strategy_code` parameter; if present, skip `_default_quant_coder` for iteration 1
4. In `run_pipeline.py`, pass the simulator's strategy code to the research endpoint

---

## FP-3 🟡 News LLM Calls Are Sequential

**Component:** `vinu-news`
**Files:** `run_pipeline.py:304-312`, `routes_read.py:150-159`

**Problem:**
`step_news` iterates `for article in articles[:article_count]: POST /news/analyze` — each HTTP call blocks for the full LLM latency before the next starts. N articles = N sequential LLM calls.

**Impact:** 5 articles = 5× LLM latency (~30s) instead of 1× (~6s).

**Fix Plan:**
1. Change the pipeline to fire N concurrent requests using `concurrent.futures.ThreadPoolExecutor`:
   ```python
   with ThreadPoolExecutor(max_workers=article_count) as pool:
       futures = [pool.submit(lambda a: requests.post(f"{base}/news/analyze",
           json={"url_or_id": a["url"]}, timeout=300)) for a in articles]
       for f in concurrent.futures.as_completed(futures):
           if f.result().status_code == 200:
               analyzed += 1
   ```
2. Alternatively, expose a batch endpoint `POST /news/analyze/batch` in the news service that processes articles in parallel internally.

---

## FP-4 🟡 Backfill Lock Returns 409 Immediately

**Component:** `vinu-stock-price`
**Files:** `routes_config.py:83-84`

**Problem:**
The backfill lock uses `acquire(blocking=False)` — if a backfill is already running, the caller gets an immediate HTTP 409 with `"Backfill already running"`. The caller has no fallback (no queue, no join, no retry).

**Impact:** Pipeline fails if run back-to-back. Also, `threading.Lock` is not shared across uvicorn worker processes.

**Fix Plan:**
1. Change to `acquire(blocking=True, timeout=300)` to wait for the existing backfill to finish
2. Track the active job_id and allow new callers to poll the same job_id instead of creating a new one
3. For multi-process safety, use a file-based lock or Redis-based lock

---

## FP-5 🟠 No Retry Logic Anywhere in Pipeline

**Component:** `run_pipeline.py`
**Files:** `run_pipeline.py:202-217, 426-471`

**Problem:**
Every step runs exactly once. `_req()` calls `raise_for_status()` with no retry. `_poll_job()` does the same. Any transient HTTP 50x, connection reset, or timeout aborts the entire pipeline.

**Impact:** 100% loss of progress (potentially 90+ seconds of work) on any hiccup.

**Fix Plan:**
1. Add a `_retry()` wrapper with exponential backoff:
   ```python
   def _retry(fn, retries=3, base_delay=1):
       for attempt in range(retries):
           try:
               return fn()
           except (requests.ConnectionError, requests.Timeout, HTTPError) as e:
               if e.response is not None and e.response.status_code < 500:
                   raise  # don't retry 4xx
               if attempt == retries - 1:
                   raise
               time.sleep(base_delay * (2 ** attempt))
   ```
2. Wrap `_req`, `_poll_job`, and step work functions with this retry helper
3. For idempotent steps (features, initial-analysis, research), add step-level retry

---

## FP-6 🟡 Research LLM Calls Are Sequential Across Iterations

**Component:** `vinu-research`
**Files:** `loop.py:191-355`, `llm_generator.py:286-292`

**Problem:**
The research loop does: generate (parallel candidates) → wait → backtest → wait → critic → wait → repeat. Each iteration fully completes before the next begins. There's no pipelining of iteration N+1's generation with iteration N's backtest.

**Impact:** For `max_iterations=5` and `llm_candidates=3`, that's 5 × (3 parallel + 1 sequential) = ~20 LLM round-trips in wall-clock time.

**Fix Plan:**
1. Start generation for iteration N+1 in parallel with iteration N's backtest (as soon as generation for iteration N is done, not after backtest + critic)
2. Use `asyncio.create_task()` to fire the next generation while running the current backtest
3. Add a configurable `concurrent_iterations` parameter

---

# Deep-Audit Findings (32 New)

---

## DA-1 🔴 PanelCache Is Dead Code in vinu-tools

**Component:** `vinu-tools`
**Files:** `engine/engine.py` (no reference), `compute/data_cache.py:18-108`

**Problem:**
`PanelCache` is fully implemented, tested, and exported — but the `FeatureEngine.process()` method in `engine.py` **never imports or calls it**. Every feature request re-fetches ALL candles from stock-api via HTTP, even if the exact same data was fetched seconds ago.

**Impact:** Each feature request makes N HTTP calls (one per symbol) × warmup bars, with zero caching. Wasted network and stock-api load.

**Fix Plan:**
1. Import `PanelCache` in `engine.py` and wire it into `_process_symbol`:
   ```python
   from vinu_tools.compute.data_cache import get_cache
   cache = get_cache()
   rows = cache.get(symbol, interval, warmup_from, request.to_ts)
   if rows is None:
       rows = self.client.fetch_candles(symbol, ...)
       cache.set(symbol, interval, warmup_from, request.to_ts, rows)
   ```
2. Make `PanelCache` TTL configurable via env var
3. Test that repeated identical feature requests hit the cache

---

## DA-2 🔵 Sentiment Scores Are Integer by Design (False Positive)

**Component:** `vinu-news`
**Files:** `analysis/enrichment/sentiment.py:247-290`, `analysis/storage/schema.sql:15`

**Investigation Findings:**
The original audit claimed sentiment scores are floats truncated to 0 by the `INTEGER` column. This is incorrect:

1. **Scores are integers, not floats.** The rule-based `score_sentiment()` function computes `net = pos - neg` where each keyword adds ±1/±2/±3. There are no floats involved. Realistic scores are -7 to +7.
2. **SQLite INTEGER stores arbitrary integers.** SQLite has dynamic type affinity — it does NOT truncate integers. A score of 4 is stored as 4, not as 0 (confirmed by test).
3. **Impact thresholds are calibrated correctly.** `impact.py` uses thresholds at 3 and 6, which work as intended with integer scores.

**Verdict: False positive.** No data corruption exists. The INTEGER column is appropriate for rule-based scores. The only caution is a separate LLM sentiment score (float -1.0 to +1.0) stored in `news_analysis.analysis_json` — if that were ever mixed into `articles.sentiment_score`, it would need a REAL column.

---

## DA-3 🔴 Watchlist Shared File Has No Locking (Data Loss)

**Component:** `vinu-news` (shared file), affects all services
**Files:** `watchlist/shared.py:14-28`, `service.py:323-329`

**Problem:**
`write_shared()` uses `Path.write_text(json.dumps(data))` with no temporary file, no atomic rename, no file lock. Concurrent writes from news-api + stock-api + strategy-api can silently lose tickers:
- Process A reads `[AAPL, MSFT]`
- Process B reads `[AAPL, GOOG]`
- Process A writes `[AAPL, MSFT]` (loses GOOG)
- Process B writes `[AAPL, GOOG]` (loses MSFT)

**Impact:** Tickers silently disappear from the watchlist. No error raised. Users may not notice for days.

**Fix Plan:**
1. Use atomic write pattern:
   ```python
   tmp = path.with_suffix(".tmp")
   tmp.write_text(json.dumps(data))
   tmp.rename(path)  # atomic on POSIX
   ```
2. Add a file-level lock (e.g., `portalocker` or `fcntl.flock`)
3. Alternatively, replace the shared file with a shared SQLite database or Redis

---

## DA-4 🟠 `--incremental` Is Dead Code in vinu-initial-analysis

**Component:** `vinu-initial-analysis`
**Files:** `cli.py:95-107`

**Problem:**
The CLI accepts `--incremental` / `--no-incremental` flags. The `_compute_batch` function receives `incremental` as a parameter. But **it is never passed to `runner.run()`**. The parameter is completely ignored. Every compute cycle is a full recompute.

**Impact:** Users think they're running incrementally but every run re-fetches all data and re-computes all 25 angles.

**Fix Plan:**
1. Thread the `incremental` flag through to `runner.run()`
2. In `runner.run()`, when `incremental=True`, skip re-computing angles that already have results for the same date range
3. Check `AngleStorage.read()` for existing results before re-computing

---

## DA-5 🟠 HTTP Calls Have No Timeout in vinu-initial-analysis

**Component:** `vinu-initial-analysis`
**Files:** `net.py:23-33`, `clients/news_client.py`, `clients/price_client.py`

**Problem:**
All HTTP client calls use `requests.request(method, url, **kwargs)` with **no `timeout` parameter**. If stock-api or news-api hangs (e.g., due to database contention, slow provider), the request blocks indefinitely, tying up the compute worker or API handler forever.

**Impact:** A single hung request can stall the entire compute pipeline or ASGI thread pool indefinitely.

**Fix Plan:**
1. Add `timeout=30` to all `request()` calls in `net.py`
2. Make timeout configurable via config/env var
3. Add a connection-level timeout + read timeout (e.g., `(5, 25)`)

---

## DA-6 🟠 ALL API Routes Block ASGI Event Loop

**Component:** `vinu-initial-analysis`
**Files:** `routes_read.py:21-87`

**Problem:**
Every route handler is `async def` but calls synchronous blocking I/O directly without `run_in_executor`. For example:
```python
@router.get("/impact/{ticker}")
async def get_impact(...):
    return svc.get_impact(...)  # BLOCKS event loop - sync parquet read
```
The `POST /run/{ticker}` endpoint runs the entire multi-minute compute pipeline synchronously inside the single event loop thread.

**Impact:** During a compute pipeline run, ALL other API requests are blocked. The server appears dead to other clients.

**Fix Plan:**
1. Wrap all blocking calls with `run_in_executor`:
   ```python
   @router.get("/impact/{ticker}")
   async def get_impact(...):
       svc = _get_svc()
       loop = asyncio.get_running_loop()
       return await loop.run_in_executor(None, svc.get_impact, ticker.upper(), from_ts, to_ts)
   ```
2. For `POST /run/{ticker}`, submit to a background thread and return a job_id immediately (fire-and-forget with status endpoint)

---

## DA-7 🟠 Weight Storage Reads ALL Parquet Files Then Filters

**Component:** `vinu-strategy`
**Files:** `weights.py:66-104`

**Problem:**
`read_weights()` iterates all year/month/day parquet directories, reads **every** parquet file into memory via `pq.read_table()`, concatenates all tables, converts to pandas, and **then** filters by symbol/date. After 3 years of daily evaluation, that's ~1095 files loaded on every weight query.

**Impact:** Weight queries get slower over time. A single-symbol narrow-date-range query loads the entire history.

**Fix Plan:**
1. Push filtering to the file-globbing level: only glob files within the requested date range
2. Use DuckDB to read parquet files with predicate pushdown instead of pandas
3. Add periodic compaction: merge daily files into monthly/yearly files
4. Add an index (SQLite or DuckDB) mapping symbol→date→file_path for O(1) file lookup

---

## DA-8 🟠 Research Has No `strategy_code` Parameter

**Component:** `vinu-research`
**Files:** `routes_read.py:17-35`, `service.py:57-67`

**Problem:**
The `RunResearchRequest` model has no `strategy_code` field. There is no way to submit a pre-written strategy for evaluation-only without the LLM generating from scratch. Users must go to the simulator directly if they have existing code.

**Impact:** Cannot re-evaluate or backtest existing strategies through the research service. Every run is a full LLM-based research cycle.

**Fix Plan:**
1. Add `strategy_code: str | None = None` to `RunResearchRequest`
2. In `service.run_research()`, if `strategy_code` is provided, pass it as `initial_strategy_code` to the loop
3. In `loop.run()`, if `initial_strategy_code` is set, skip `_default_quant_coder` for iteration 1 and use the provided code directly
4. Add an endpoint `POST /research/evaluate` for lightweight evaluation without LLM

---

## DA-9 🟠 LLM Refinement Failure Generates Fresh Template Strategy

**Component:** `vinu-research`
**Files:** `loop.py:776`

**Problem:**
When LLM refinement returns empty candidates (e.g., after a transient failure), the fallback code calls `generate_strategy(recipe=recipe, ...)` which produces a **completely new template strategy**. It then injects filter lines from the previous critique into this unrelated template. The critique's suggestions were about a completely different codebase.

**Impact:** The refinement chain is broken. The template strategy may behave entirely differently from the strategy the critique evaluated, leading to nonsensical iteration sequences.

**Fix Plan:**
1. Save the last successfully generated strategy code in loop state
2. On LLM failure, return the **previous iteration's code** with filters applied, not a fresh template
3. Add a retry (1-2 attempts) before falling back
4. If no fallback is available, log a warning and continue with the previous code unchanged

---

## DA-10 🟠 Recipe Over-Computation in vinu-tools

**Component:** `vinu-tools`
**Files:** `compute/registry.py:346-385`

**Problem:**
When any single factor from alpha101 is requested, `recipe_catalog.compute_recipe(rows, "alpha101_benchmark")` computes **all 101 factors**. Same for alpha158 (158 factors) and alpha360 (360 factors). Most of the computed columns are then discarded.

**Impact:** For a pipeline requesting `["alpha101_rank_sma_20"]`, ~100× more compute than necessary is performed.

**Fix Plan:**
1. Add `lazy=True` parameter to `compute_recipe` — compute only the requested columns by tracing their dependency graph
2. If lazy computation is not feasible, add PCA/pre-computation so only needed factors are materialized
3. At minimum, document which recipes are "all-or-nothing" so users can make informed choices

---

## DA-11 🟠 All Stock-Price Routes Block ASGI Event Loop

**Component:** `vinu-stock-price`
**Files:** `routes_read.py:37-65`, `routes_config.py:33-117`

**Problem:**
`GET /candles/{symbol}` reads parquet files, aggregates 1m→higher in Python, computes RSI/MACD — all synchronously. All route handlers are `def` (sync), meaning they block the uvicorn worker thread pool. A `/candles` request for multi-year daily data can take seconds.

**Impact:** Under concurrent load, one slow `/candles` request blocks other requests in the same thread pool.

**Fix Plan:**
1. Convert heavy routes to `async def` and use `run_in_executor`:
   ```python
   @router.get("/candles/{symbol}")
   async def candles(symbol, ...):
       loop = asyncio.get_running_loop()
       return await loop.run_in_executor(None, get_service().get_candles, symbol, ...)
   ```
2. Move aggregation from Python to DuckDB SQL (see DA-12)
3. Add response caching for frequently-requested candle ranges (Redis or in-memory with TTL)

---

## DA-12 🟠 DuckDB Aggregation Done in Python Instead of SQL

**Component:** `vinu-stock-price`
**Files:** `query/aggregate.py:27-54`, `query/engine.py:69-74`

**Problem:**
When requesting 1d candles, the engine reads ALL 1m bars from DuckDB into Pandas, converts to `list[dict]`, then iterates in Python to bucket-aggregate by day. DuckDB can do this natively with `GROUP BY bar_ts / interval_sec` — without leaving C++.

**Impact:** Orders of magnitude slower than native DuckDB aggregation. Memory overhead from Pandas + list conversion.

**Fix Plan:**
1. Generate DuckDB SQL that aggregates at query time:
   ```sql
   SELECT symbol, provider,
       (bar_ts / {interval_sec}) * {interval_sec} AS bar_ts,
       FIRST(open) AS open, MAX(high) AS high,
       MIN(low) AS low, LAST(close) AS close,
       SUM(volume) AS volume
   FROM read_parquet([...], union_by_name=true)
   WHERE symbol = ? AND bar_ts >= ? AND bar_ts < ?
   GROUP BY symbol, provider, bar_ts
   ORDER BY bar_ts
   ```
2. Only fall back to Python aggregation for exotic intervals not expressible in SQL
3. Stream results back instead of loading everything into memory first

---

## DA-13 🟠 `_bar_cache` Cleared at Start of Every `run()` Call

**Component:** `vinu-initial-analysis`
**Files:** `runner.py:89`

**Problem:**
The `_bar_cache` dict caches bars by `(symbol, time_format)` within a single `run()` call. But it's **cleared at the start of every `run()`** (line 89: `self._bar_cache.clear()`). This means every call to `run(symbol)` re-fetches bars from the network, even if the same symbol was just computed 1 second ago.

**Impact:** Re-running analysis on the same symbol fetches identical bars over the network each time.

**Fix Plan:**
1. Move `_bar_cache` to instance level (not cleared per-run)
2. Make it a proper LRU cache with TTL (e.g., 5 minutes)
3. Key by `(symbol, time_format, from_ts, to_ts)` for granular cache invalidation

---

## DA-14 🟠 Parquet Files Accumulate Unbounded in vinu-initial-analysis

**Component:** `vinu-initial-analysis`
**Files:** `storage/parquet.py:58`, `runner.py:145-152`

**Problem:**
Every `run()` creates a **new parquet file** per angle per symbol. There is no compaction, no retention policy, no merging of old files. The `read()` function loads ALL files into memory and concatenates them. After 100 runs, 100 files are read per query.

**Impact:** Storage grows linearly with runs. Query time and memory grow linearly too.

**Fix Plan:**
1. Add a compaction step that merges parquet files after N runs (e.g., threshold=10)
2. Add a retention policy: keep last K runs or runs newer than T days
3. Implement incremental writes: write new data to a "delta" file, periodically merge into a "base" file
4. Add a query-time file filter: only read files created after the requested date range

---

## DA-15 🟡 Strategy Service Has No Warm-Up Mechanism

**Component:** `vinu-strategy`
**Files:** `service.py:44-128`

**Problem:**
The first evaluation of a strategy has zero historical weight data. Features are fetched snapshot-only (not time series). The `WeightStorage` starts empty. There's no baseline or initialization period.

**Impact:** The first evaluation produces weights with no historical context. Strategies that depend on trailing values (SMA crossovers, momentum) produce unreliable initial signals.

**Fix Plan:**
1. Add a warm-up mode that backfills historical features and runs evaluations for a "burn-in" period
2. Accept an optional `from_date` on the evaluate endpoint to auto-backfill weights from that date
3. Store features as time series (not just latest snapshot) to enable trailing-window strategies

---

## DA-16 🟡 Per-Symbol Sequential HTTP for Price Data in Simulator

**Component:** `vinu-simulator`
**Files:** `price_client.py:24-48, 79-99`

**Problem:**
Both `get_ohclv()` and `_fetch_price_data()` iterate over symbols ONE AT A TIME, making a separate HTTP request per symbol. For 500 symbols, that's 500 sequential round-trips at ~50ms each = 25 seconds of data-loading time.

**Impact:** Simulation startup is O(N) in the number of symbols, even though the upstream API could support batch requests.

**Fix Plan:**
1. Use `ThreadPoolExecutor` to fetch symbols in parallel:
   ```python
   with ThreadPoolExecutor(max_workers=10) as pool:
       futures = {pool.submit(self.get, f"/candles/{sym}", params): sym for sym in symbols}
       for future in as_completed(futures):
           sym = futures[future]
           result[sym] = future.result()
   ```
2. Better yet, add a batch endpoint `POST /candles/batch` to stock-api that accepts `symbols: list[str]` and returns all at once

---

## DA-17 🟡 No Caching of Simulation Results for Identical Inputs

**Component:** `vinu-simulator`
**Files:** `service.py:38-144, 146-272`

**Problem:**
Both `simulate()` and `simulate_custom()` run the full pipeline every time — OHLCV fetching, weight fetching, engine run, validation, Monte Carlo — with no content-addressed cache. Identical requests are recomputed from scratch.

**Impact:** Re-running the same simulation wastes CPU, network, and time (potentially minutes).

**Fix Plan:**
1. Compute a content hash of `(strategy_code/name, symbols, from_date, to_date, interval, initial_capital, ...)`
2. Before running, check `ResultStorage` for an existing result with the same hash
3. If found and within TTL, return cached result
4. Invalidate cache when underlying price/feature data changes (via version counter or timestamp)

---

## DA-18 🟡 `weights_hist` Stored as Python List (3-4× Memory Overhead)

**Component:** `vinu-simulator`
**Files:** `simulator.py:125, 267`

**Problem:**
The simulation engine accumulates weight history as:
```python
weights_hist.append(w.tolist())  # numpy array → Python list of floats
```
Python `float` objects are ~28 bytes each vs 8 bytes for numpy float64. For 35K rows × 100 symbols, this is ~98 MB in Python lists vs ~28 MB in numpy arrays.

**Impact:** Memory usage 3-4× higher than necessary for weight history storage.

**Fix Plan:**
1. Change `weights_hist` to accumulate numpy arrays directly:
   ```python
   weights_hist.append(w)  # keep as numpy array
   ```
2. At the end, convert to a single matrix with `np.stack(weights_hist, axis=0)` instead of casting each row to list
3. Do the same for `_equity_curve` in `SimulatorEnv`

---

## DA-19 🟡 BaseClient Thread Lock Serializes Concurrent Requests

**Component:** `vinu-simulator`
**Files:** `base.py:12-22`

**Problem:**
`BaseClient` wraps all HTTP requests with `threading.Lock()`. This serializes every call to the same client. With `PriceClient.get()` needing 500 sequential calls (from DA-16), all other concurrent simulation requests block on the same lock.

**Impact:** Concurrent simulation requests contend on the same lock rather than running independently.

**Fix Plan:**
1. Remove the thread lock from `BaseClient`
2. Use `httpx.Client`'s built-in connection pooling (safe for concurrent use with thread limits)
3. Or, use separate client instances per request

---

## DA-20 🟡 Walk-Forward Windows Run Sequentially

**Component:** `vinu-research`
**Files:** `loop.py:549-595`

**Problem:**
Each walk-forward window (3 windows × 2 backtests = 6 total) runs sequentially. There is no data dependency between windows — window 2 does not need window 1's results.

**Impact:** 6 sequential backtest calls = 6-30 seconds that could run in parallel.

**Fix Plan:**
1. Use `asyncio.gather` to run all windows in parallel:
   ```python
   tasks = []
   for w in windows:
       tasks.append(asyncio.gather(
           self._run_backtest(...),  # in-sample
           self._run_backtest(...),  # out-of-sample
       ))
   results = await asyncio.gather(*tasks)
   ```
2. Collect results preserving window order

---

## DA-21 🟡 `best_result` Is Last Iteration, Not Truly Best

**Component:** `vinu-research`
**Files:** `loop.py:333-348`

**Problem:**
`best_result = result` is set on **every** iteration at line 333, **before** the improvement check at line 347. If iteration 3 has Sharpe 1.2 but iteration 4 drops to 0.9 and the improvement check stops the loop, `best_result` points to iteration 4 (0.9), not iteration 3 (1.2).

**Impact:** The research report shows a suboptimal strategy as "best."

**Fix Plan:**
1. Only update `best_result` when the new result is better:
   ```python
   if best_result is None or result.metrics.sharpe_ratio > best_result.metrics.sharpe_ratio:
       best_result = result
       best_iteration = iteration
   ```
2. Compare using a composite score (Sharpe × WinRate / MaxDD) rather than raw ordering

---

## DA-22 🟡 No Retry on Transient LLM Failure in Research

**Component:** `vinu-research`
**Files:** `llm_generator.py:294-300`

**Problem:**
When `asyncio.gather` returns an exception for a candidate, it's logged and skipped — with **no retry**. If the LLM server had a transient spike, that candidate slot is permanently lost. For `n_candidates=3`, if 2 fail, only 1 candidate competes.

**Impact:** Fewer candidates leads to lower quality strategies. Complete failure returns no candidates.

**Fix Plan:**
1. Add per-candidate retry with backoff:
   ```python
   async def _generate_with_retry(self, ...):
       for attempt in range(3):
           try:
               return await self._generate_one(...)
           except Exception:
               if attempt == 2:
                   raise
               await asyncio.sleep(1 * (2 ** attempt))
   ```
2. Configure max_retries per candidate via env var

---

## DA-23 🟡 Backfill Skips Chunks on HTTP Error (Silent Data Gaps)

**Component:** `vinu-news`
**Files:** `service.py:398-427`

**Problem:**
When `registry.fetch_for_ticker()` returns an empty list (HTTP error, timeout, provider down), the backfill loop treats it as "no articles in this time window" and moves to the next chunk: `chunk_start = chunk_end`. The error is **not logged, not stored in `error_message`**, and the gap is silently skipped.

**Impact:** Historical data has silent gaps. Users have no way to know articles are missing for specific periods.

**Fix Plan:**
1. Differentiate between "empty response" and "error response" in the backfill loop
2. On HTTP error, log the error, record it in the backfill status `error_message` field, and retry the chunk after a delay
3. Add a setting `backfill_max_retries` with exponential backoff
4. Show error messages in the backfill status API response

---

## DA-24 🟡 N+1 Query in `get_news_for_watchlist`

**Component:** `vinu-news`
**Files:** `sqlite_backend.py:191-211`

**Problem:**
`get_news_for_watchlist()` iterates over each ticker and calls `get_news_for_ticker(symbol, ...)` individually. For a watchlist of 50 tickers, that's **50 separate SQL queries** instead of one `WHERE m.ticker IN (?, ?, ...)` query.

**Impact:** Watchlist-wide queries get slower linearly with watchlist size. At 500 tickers, 500 sequential SQL queries.

**Fix Plan:**
1. Rewrite `get_news_for_watchlist()` to use a single query with `WHERE ticker IN ({placeholders})`
2. Add a covering index on `(ticker, published_at)` for sorted news retrieval

---

## DA-25 🟡 On-Demand + Auto-Analysis Can Race for Same Article

**Component:** `vinu-news`
**Files:** `analysis/llm/analyze.py:35-48`, `service.py:70-91`

**Problem:**
The on-demand `/news/analyze` endpoint and the background auto-analysis worker can analyze the **same article concurrently**:
1. Both check cache → both miss
2. Both call LLM → double cost
3. Both write to cache → last write wins (same result, but cost doubled)

The cache check-and-set is not in a critical section, so there's no prevention.

**Impact:** Wasted LLM tokens. At $0.50-2.00 per million tokens, this adds up.

**Fix Plan:**
1. Use a SQLite-level `INSERT OR IGNORE` transaction for cache writes (first writer wins)
2. Add an in-memory `lock per article URL` using `threading.Lock` in a dict
3. Only the first writer calls the LLM; subsequent callers wait for the result

---

## DA-26 🟡 `_background_jobs` Dict Grows Unbounded

**Component:** `vinu-stock-price`
**Files:** `routes_config.py:22-24, 86-114`

**Problem:**
Every `POST /backfill/trigger` and `POST /ingest/trigger` adds an entry to the `_background_jobs` dict that is **never removed**. Old completed/failed jobs accumulate until the server restarts.

**Impact:** Memory leak. After thousands of triggers (over days), the dict consumes significant memory.

**Fix Plan:**
1. Add a cleanup task that removes entries older than a configurable TTL (e.g., 1 hour)
2. On new trigger, prune oldest entries if the dict size exceeds a threshold (e.g., 1000 entries)
3. Use `OrderedDict` and pop oldest when full

---

## DA-27 🟡 Backfill Sets "complete" Even When Some Years Failed

**Component:** `vinu-stock-price`
**Files:** `orchestrator.py:103-116`

**Problem:**
After the per-year loop, `catalog.upsert_symbol(sym, backfill_status="complete")` is called unconditionally. If year 2022 succeeded but 2023 failed, the symbol's status is still set to `"complete"`. Later, `get_pending_backfill_symbols()` sees `"complete"` and will never retry the failed year.

**Impact:** Failed years are silently buried. Data gaps are permanent unless manually re-triggered.

**Fix Plan:**
1. Only set `"complete"` if `summary.years_failed == 0`
2. If some years failed, set `"partial"` and record which years failed in a new column `failed_years: list[int]`
3. Add a retry mechanism specifically for failed years (not a full re-backfill)

---

## DA-28 🟡 No Completeness Check Before Re-Download

**Component:** `vinu-stock-price`
**Files:** `orchestrator.py:78-116`

**Problem:**
`_backfill_symbol()` has **no early-exit check** for already-complete symbols. Even if a symbol has `backfill_status="complete"` with all years present, the code:
1. Overwrites status to `"partial"` (line 78)
2. Re-reads `first_bar_ts` (lines 82-84)
3. Re-downloads every year from `start_year` to `end_year` (line 91)
4. Reads the existing parquet, merges, dedupes, re-writes it
5. Sets status back to `"complete"`

**Impact:** Every backfill cycle fully re-downloads all symbols, even cached ones. Massive redundant I/O and API usage.

**Fix Plan:**
1. Add early return at the top of `_backfill_symbol`:
   ```python
   entry = catalog.get_symbol(sym)
   if entry and entry.backfill_status == "complete":
       if from_year is None and to_year is None:
           return  # skip already-complete symbols
   ```
2. When `from_year` or `to_year` is specified, only re-download that range

---

## DA-29 🟠 No Timeout on Symbol Fetch Futures

**Component:** `vinu-tools`
**Files:** `engine/engine.py:77`

**Problem:**
`ThreadPoolExecutor.submit()` returns a future, and `future.result()` is called with **no timeout**. If a single symbol's candle fetch hangs (DNS, TCP timeout, upstream dead), the entire `process()` call hangs forever, blocking the worker thread.

**Impact:** A single hung symbol fetch holds the worker thread indefinitely. Other jobs in the queue never get processed.

**Fix Plan:**
1. Add `future.result(timeout=120)` to all symbol fetch futures
2. On timeout, log the symbol and mark it as failed, allowing other symbols to complete
3. Set a global per-request timeout from the API layer

---

## DA-30 🟠 Sync HTTP Call in Sync Route Blocks ASGI

**Component:** `vinu-tools`
**Files:** `routes_features.py:30-94`

**Problem:**
`GET /features/{symbol_or_kind}` is a **sync `def`** handler that calls `httpx.get()` inside it, blocking the uvicorn worker thread pool. Under load, this endpoint starves other requests.

**Impact:** Same as DA-11 — ASGI thread pool starvation under concurrent load.

**Fix Plan:**
1. Convert to `async def` and use `httpx.AsyncClient` (already imported in some places)
2. Add a timeout to the upstream HTTP call
3. Use connection pooling with `httpx.AsyncClient` as a singleton

---

## DA-31 🟠 Upstream Errors Silently Return 200 OK With Empty Data

**Component:** `vinu-tools`
**Files:** `routes_features.py:91-94`

**Problem:**
```python
except Exception as exc:
    logger.error(...)
    return {"symbol": symbol_or_kind, "values": {}, "signal": 0.0}
```
All upstream errors (timeout, DNS failure, HTTP 500, parse error) are caught and return a **200 OK** with empty data. The caller cannot distinguish "no data" from "upstream is down."

**Impact:** Silent failures mask upstream outages. Downstream services (strategy, portfolio) get empty features and produce wrong signals without any indication of the root cause.

**Fix Plan:**
1. Return HTTP 502 or 503 on upstream errors instead of 200 with empty data
2. Add a `status` field to the response: `{"status": "error", "code": "UPSTREAM_DOWN", ...}`
3. Log the full error context (host, path, timing, response body snippet)

---

## DA-32 🟡 No Cross-Request Feature Caching in vinu-tools

**Component:** `vinu-tools`
**Files:** `engine/engine.py:41-103`, `service.py:124-127`

**Problem:**
The dedup hash only catches **exact** duplicates (same features, symbols, interval, date range). Requesting `[rsi_14, sma_20]` does not reuse results from a prior request for `[rsi_14]`, even though the RSI data is identical. There is no piecewise caching: each feature request is an all-or-nothing computation.

**Impact:** 2×-10× redundant computation when overlapping feature sets are requested.

**Fix Plan:**
1. Store computed features in a shared columnar store (DuckDB or SQLite with parquet) keyed by `(symbol, interval, timestamp, feature_name)`
2. Before computing, check which features are already stored and only compute the delta
3. Implement a feature-level cache TTL (features only invalidate when underlying price data changes)

---

# Summary by Component

| Component | Finding IDs | Critical | High | Medium | Low |
|-----------|-------------|----------|------|--------|-----|
| **vinu-stock-price** | FP-1, FP-4, DA-11, DA-12, DA-26, DA-27, DA-28 | — | 4 | 2 | 1 |
| **vinu-news** | FP-3, DA-2, DA-3, DA-23, DA-24, DA-25 | 1 | 1 | 2 | 2 |
| **vinu-tools** | DA-1, DA-10, DA-29, DA-30, DA-31, DA-32 | 1 | 3 | 2 | — |
| **vinu-initial-analysis** | DA-4, DA-5, DA-6, DA-13, DA-14 | — | 3 | 2 | — |
| **vinu-strategy** | DA-7, DA-15 | — | 1 | 1 | — |
| **vinu-simulator** | DA-16, DA-17, DA-18, DA-19 | — | 1 | 3 | — |
| **vinu-research** | FP-2, FP-6, DA-8, DA-9, DA-20, DA-21, DA-22 | — | 2 | 4 | 1 |
| **run_pipeline.py** | FP-5 | — | 1 | — | — |
| **vinu-infra (shared)** | (none in scope) | — | — | — | — |

# Severity Totals

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 2 |
| 🟠 HIGH | 18 |
| 🟡 MEDIUM | 14 |
| 🔵 LOW | 4 |
| **Total** | **38** |

---

# Recommended Fix Priority

## Sprint 1 (Data Integrity & Critical Bugs)
1. 🔴 DA-3: Atomic watchlist writes + file locking (data loss)
2. 🔴 DA-1: Wire PanelCache into engine.py (dead caching layer)
4. 🟠 DA-23: Fix silent backfill gaps in news
5. 🟠 DA-27: Fix backfill "complete" status when years fail

## Sprint 2 (Pipeline Reliability)
6. 🟠 FP-5: Add retry logic to pipeline steps
7. 🟠 DA-5: Add HTTP timeouts to initial-analysis client
8. 🟠 DA-6: Move sync blocking I/O to `run_in_executor`
9. 🟠 DA-22: Add retry on LLM failure in research
10. 🟠 DA-29: Add timeout on symbol fetch futures

## Sprint 3 (Performance — Biggest Wins)
11. 🟠 FP-1: Backfill only requested ticker
12. 🟠 DA-12: Push aggregation to DuckDB SQL
13. 🟠 DA-7: Push-down filtering in weight storage
14. 🟡 DA-16: Parallelize per-symbol HTTP in simulator
15. 🟠 DA-8: Add strategy_code parameter to research endpoint

## Sprint 4 (Medium Impact)
16. 🟠 FP-2: Research reuses simulator results
17. 🟡 FP-3: Parallelize news analysis
18. 🟡 DA-13: Don't clear _bar_cache per run
19. 🟡 DA-17: Cache simulation results for identical inputs
20. 🟡 DA-20: Parallelize walk-forward windows

## Sprint 5 (Cleanup & Polish)
21. 🟡 DA-4: Wire incremental flag through initial-analysis
22. 🟡 DA-21: Fix best_result tracking in research loop
23. 🟡 DA-32: Add feature-level caching in vinu-tools
24. 🔵 Remaining LOW severity items
