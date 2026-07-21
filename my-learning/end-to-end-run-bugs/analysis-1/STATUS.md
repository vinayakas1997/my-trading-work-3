# Inefficiency Fix — Status Tracker

**Total:** 52 | **Completed:** 31 | **In Progress:** 0 | **Invalid:** 2 | **Pending:** 19

> Update this file after fixing each problem — mark `Completed` and add the date.

---

## First-Pass Findings

| ID | Title | Severity | Component | Status | Date Fixed | Notes |
|----|-------|----------|-----------|--------|------------|-------|
| FP-1 | Backfill Triggers ALL Symbols | 🔴 CRITICAL | vinu-stock-price | Completed | 2026-07-21 | Pass ticker via JSON body, pending-only fallback, completeness guard, auto-rollover + shard consolidation |
| FP-2 | Research Ignores Prior Simulation Results | 🟠 HIGH | vinu-research | Completed | 2026-07-21 | Pipeline now passes simulator strategy_code to research; fix variable shadowing bug in loop.py |
| FP-3 | News LLM Calls Are Sequential | 🟡 MEDIUM | vinu-news | Pending | — | — |
| FP-4 | Backfill Lock Returns 409 Immediately | 🟡 MEDIUM | vinu-stock-price | Pending | — | — |
| FP-5 | No Retry Logic Anywhere in Pipeline | 🟠 HIGH | run_pipeline.py | Pending | — | — |
| FP-6 | Research LLM Calls Are Sequential Across Iterations | 🟡 MEDIUM | vinu-research | Pending | — | — |

## Deep-Audit Findings

### Critical

| ID | Title | Severity | Component | Status | Date Fixed | Notes |
|----|-------|----------|-----------|--------|------------|-------|
| DA-1 | PanelCache Is Dead Code | 🔴 CRITICAL | vinu-tools | Completed | 2026-07-21 | Deleted data_cache.py (120 lines of dead code) |
| DA-2 | Sentiment Scores Truncated to 0 | 🔵 LOW | vinu-news | Invalid | — | False positive — scores are integers by design, SQLite INTEGER stores them correctly. No truncation occurs. |
| DA-3 | Watchlist Shared File Has No Locking | 🔴 CRITICAL | vinu-news | Completed | 2026-07-21 | Atomic writes (tmp + os.replace) + filelock on read/write, corrupted JSON handling |

### High

| ID | Title | Severity | Component | Status | Date Fixed | Notes |
|----|-------|----------|-----------|--------|------------|-------|
| DA-4 | `--incremental` Is Dead Code | 🟠 HIGH | vinu-initial-analysis | Completed | 2026-07-21 | Removed flag from CLI, param from api.py + service.py |
| DA-5 | HTTP Calls Have No Timeout | 🟠 HIGH | vinu-initial-analysis | Completed | 2026-07-21 | Added default timeout=(5,30) to net.request() |
| DA-6 | ALL API Routes Block ASGI Event Loop | 🟠 HIGH | vinu-initial-analysis | Completed | 2026-07-21 | Changed async def → def on all 14 route handlers |
| DA-7 | Weight Storage Reads ALL Parquet Files Then Filters | 🟠 HIGH | vinu-strategy | Completed | 2026-07-21 | Dir pruning + PyArrow predicate pushdown in _collect_tables |
| DA-8 | Research Has No `strategy_code` Parameter | 🟠 HIGH | vinu-research | Completed | 2026-07-21 | Added optional strategy_code input at all 4 layers (API, service, loop, CLI) |
| DA-9 | LLM Refinement Failure Generates Fresh Template Strategy | 🟠 HIGH | vinu-research | Completed | 2026-07-21 | Fall back to previous_code when LLM refinement returns empty; preserve template mode behavior |
| DA-10 | Recipe Over-Computation | 🟠 HIGH | vinu-tools | Completed | 2026-07-21 | Added subset param to compute_alpha, compute_recipe, and 3 alpha recipe modules; registry passes requested subset instead of computing all |
| DA-11 | All Stock-Price Routes Block ASGI Event Loop | 🟠 HIGH | vinu-stock-price | Invalid | — | False positive — all 12 handlers are already def (sync), FastAPI threadpool is correct |
| DA-12 | DuckDB Aggregation Done in Python Instead of SQL | 🟠 HIGH | vinu-stock-price | Completed | 2026-07-21 | Dual SQL paths: non-1m pushes OHLCV aggregation + adj_factor + LIMIT into DuckDB; 390x less data transfer for daily queries |
| DA-43 | Indicators Computed in Python Loops Instead of DuckDB Window Functions | 🟡 MEDIUM | vinu-stock-price | Pending | — | SMA/RSI/MACD computed via Python loops; DuckDB window functions could be 10-100x faster |
| DA-44 | `read_bars`/`write_bars` Full Python Round-Trip | 🟡 MEDIUM | vinu-stock-price | Pending | — | Parquet→Arrow→dict→dataclass; 175k BarRecord objects per year for backfill |
| DA-45 | `append_bars` Reads Existing Day Shard to Add ~1-10 Rows | 🟡 MEDIUM | vinu-stock-price | Completed | 2026-07-21 | Skip read+dedup in append_bars; write new bars directly. DuckDB QUALIFY handles dedup at query time |
| DA-46 | IndicatorCache Not Thread-Safe | 🟡 MEDIUM | vinu-stock-price | Completed | 2026-07-21 | Added threading.Lock to protect all OrderedDict mutations |
| DA-47 | CLI Creates 3 DuckDB Connections Per 60s Cycle | 🟡 MEDIUM | vinu-stock-price | Completed | 2026-07-21 | Restructured ingest loop to use a single StockService() instead of creating 3 per cycle |
| DA-23 | Backfill Skips Chunks on HTTP Error (Silent Data Gaps) | 🟠 HIGH | vinu-news | Completed | 2026-07-21 | Return (articles, errors) tuple, retry failed chunks once, conditional mark_completed, track feeds_failed in ingestion |
| DA-33 | LLM Analysis Has No Backfill for Unanalyzed Articles | 🟠 HIGH | vinu-news | Completed | 2026-07-21 | Auto-backfill on worker startup + mode toggle, API endpoint, CLI command |
| DA-37 | Full Validation Suite Runs on Every Simulation | 🟠 HIGH | vinu-simulator | Completed | 2026-07-21 | Added run_validation=False param; validation suite skipped by default since results only go to run_card on disk |
| DA-27 | Backfill Sets "complete" Even When Some Years Failed | 🟠 HIGH | vinu-stock-price | Completed | 2026-07-21 | Conditional final status, skip done years on retry, remove redundant year_job status |
| DA-29 | No Timeout on Symbol Fetch Futures | 🟠 HIGH | vinu-tools | Completed | 2026-07-21 | Added timeout=120 to future.result() in engine.py |
| DA-30 | Sync HTTP Call in Sync Route Blocks ASGI | 🟠 HIGH | vinu-tools | Completed | 2026-07-21 | def→async def, httpx.get()→httpx.AsyncClient().get() |
| DA-31 | Upstream Errors Silently Return 200 OK With Empty Data | 🟠 HIGH | vinu-tools | Completed | 2026-07-21 | Return HTTP 502 (Bad Gateway) on upstream failure instead of 200 empty |

### Medium

| ID | Title | Severity | Component | Status | Date Fixed | Notes |
|----|-------|----------|-----------|--------|------------|-------|
| DA-13 | `_bar_cache` Cleared at Start of Every `run()` Call | 🟡 MEDIUM | vinu-initial-analysis | Pending | — | — |
| DA-14 | Parquet Files Accumulate Unbounded | 🟡 MEDIUM | vinu-initial-analysis | Pending | — | — |
| DA-15 | Strategy Service Has No Warm-Up Mechanism | 🟡 MEDIUM | vinu-strategy | Pending | — | — |
| DA-16 | Per-Symbol Sequential HTTP for Price Data in Simulator | 🟡 MEDIUM | vinu-simulator | Pending | — | — |
| DA-17 | No Caching of Simulation Results for Identical Inputs | 🟡 MEDIUM | vinu-simulator | Pending | — | — |
| DA-18 | `weights_hist` Stored as Python List (3-4× Memory Overhead) | 🟡 MEDIUM | vinu-simulator | Completed | 2026-07-21 | Store numpy arrays instead of .tolist(); np.stack at end for DataFrame |
| DA-19 | BaseClient Thread Lock Serializes Concurrent Requests | 🟡 MEDIUM | vinu-simulator | Completed | 2026-07-21 | Replaced global lock + shared httpx.Client with thread-local clients (threading.local); no lock needed |
| DA-20 | Walk-Forward Windows Run Sequentially | 🟡 MEDIUM | vinu-research | Pending | — | — |
| DA-21 | `best_result` Is Last Iteration, Not Truly Best | 🟡 MEDIUM | vinu-research | Pending | — | — |
| DA-22 | No Retry on Transient LLM Failure in Research | 🟡 MEDIUM | vinu-research | Pending | — | — |
| DA-24 | N+1 Query in `get_news_for_watchlist` | 🟡 MEDIUM | vinu-news | Completed | 2026-07-21 | Replaced N+1 loop with single `IN` query; dedup preserved |
| DA-25 | On-Demand + Auto-Analysis Can Race for Same Article | 🟡 MEDIUM | vinu-news | Completed | 2026-07-21 | Added _IN_PROGRESS set + double-check locking in analyze_article(); second caller skips duplicate LLM call |
| DA-26 | `_background_jobs` Dict Grows Unbounded | 🟡 MEDIUM | vinu-stock-price | Completed | 2026-07-21 | Added _JOBS_MAX=50 + _cleanup_old_jobs() called at all 6 assignment sites |
| DA-28 | No Completeness Check Before Re-Download | 🟡 MEDIUM | vinu-stock-price | Completed | 2026-07-21 | Already handled by FP-1 — orchestrator.py:91 has early-exit check for complete symbols |
| DA-32 | No Cross-Request Feature Caching | 🟡 MEDIUM | vinu-tools | Pending | — | — |
| DA-34 | `SELECT * FROM articles` Fetches All 23 Columns | 🟡 MEDIUM | vinu-news | Completed | 2026-07-21 | Replaced with explicit column lists across 11 SELECT sites in 3 files; added THREAD_COLUMNS + SNAPSHOT_COLUMNS constants |
| DA-35 | `SELECT *` on Threads/Snapshots Tables | 🟡 MEDIUM | vinu-news | Completed | 2026-07-21 | Combined with DA-34 — same fix with THREAD_COLUMNS + SNAPSHOT_COLUMNS |
| DA-36 | Simulator Always Computes All 30+ Metrics | 🟡 MEDIUM | vinu-simulator | Completed | 2026-07-21 | Added full_metrics=False option to skip extended metrics; propagates from API request through config to compute_full_metrics |
| DA-38 | Compute All 30+ Indicators for All Bars | 🟡 MEDIUM | vinu-initial-analysis | Pending | — | _compute_all_indicators runs on every bar but only ~10-50 peak/trough rows sampled |
| DA-39 | Read Full Parquet, Filter in Python | 🟡 MEDIUM | vinu-initial-analysis | Pending | — | get_impact/ get_correlation read entire parquet then filter; get_correlation uses last 1 row |
| DA-40 | Load Full Parquet, Convert All to Dicts | 🟡 MEDIUM | vinu-simulator | Pending | — | get_result() loads entire equity/trades parquet and to_dict all rows; callers need summary |
| DA-41 | `match_trades` Called Twice | 🟡 MEDIUM | vinu-simulator | Completed | 2026-07-21 | Added optional `round_trips` param to `by_symbol_stats()`; pass pre-computed round trips from validation |

---

## Summary

| Status | Count |
|--------|-------|
| ✅ Completed | 31 |
| 🔄 In Progress | 0 |
| ❌ Invalid | 2 |
| ⏳ Pending | 19 |
| **Total** | **52** |
