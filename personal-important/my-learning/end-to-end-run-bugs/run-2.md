# End-to-end pipeline run — status log (run 2)

**Status:** Bugs identified, fixes in progress

Ticker: `JPM`, range `2026-04-01` to `2026-07-23`. Phase 1 sample run after clearing
all old data and rebuilding all 16 Docker images.

---

## Bugs found during Phase 1 sample run

### Bug 2.1 (242/A) — NaN values in angle parquet data crash `/angle/{name}/{symbol}`

**Root cause:** `AngleStorage.read()` returns a DataFrame that may contain `NaN`
values (e.g. empty angle results, division-by-zero indicators, missing data periods).
The `get_angle` route converts this to dict with `df.to_dict("records")`, which
preserves `NaN` as `float("nan")`. FastAPI's JSON response serializer cannot handle
`NaN` values, raising `422 Unprocessable Entity` with:
```
Out of range float values are not JSON compliant: nan
```

**Status:** 🔧 Fix ready — replace NaN → None in route handler.

---

### Bug 2.2 (242/B) — `/features/{symbol}` returns 502 because `alpha158` is not a valid indicator name

**Root cause:** Research calls `/features/JPM?indicators=alpha158`. The features
route proxies to stock-api's `/candles/{symbol}` with `indicators=alpha158`.
Stock-api's `parse_indicator_names()` only knows: `sma_20, sma_50, rsi_14,
daily_return, volatility_20d`. It rejects `"alpha158"` with 400, which the features
route converts to 502.

Research's `get_feature_snapshot()` defaults to `recipe="alpha158"` — a recipe
name from the tools service, not an indicator name recognized by stock-price.

**Status:** 🔧 Fix ready — change default indicators to `"sma_20,sma_50,rsi_14"`.

---

### Bug 2.3 (242/C) — Generated strategy code has duplicate `__init__` params → `exec()` fails

**Root cause:** `generator.py::_extract_params()` uses `re.findall(r"\{(\w+)\}", body)`
which returns **all** matches including duplicates. When a template (e.g. Bollinger
Bands) has `{bb_period}` twice, the resulting `param_names = ["bb_period", "bb_period"]`.
This creates a class with `def __init__(self, bb_period=None, bb_period=None):` —
a Python `SyntaxError: duplicate argument 'bb_period' in function definition`.

The simulator's `simulate_custom()` catches the exec failure and raises
`ValueError("Failed to compile strategy code: ...")`, which the shared FastAPI
exception handler converts to 422.

**Status:** 🔧 Fix ready — deduplicate param names in `generate_strategy()`.

---

### Bug 2.4 (242/D) — Research LLM base URL uses `localhost` inside container

**Root cause:** `vinu-research/.env` has `VINU_LLM_BASE_URL=http://localhost:8009/v1`.
Inside the Docker container, `localhost` refers to the container itself, not the host.
The LLM server is on the host at port 8009.

`docker-compose.yml` already has `extra_hosts: - "host.docker.internal:host-gateway"`
for the research service, so `host.docker.internal` resolves to the host.

**Status:** 🔧 Fix ready — change `localhost` → `host.docker.internal`.

---

## Per-step status (Phase 1)

| Step | Status | Duration | Notes |
|------|--------|----------|-------|
| vinu-stock-price | ✅ | 5s | JPM backfill+ingest |
| vinu-news | ⚠️ | 180s+ | 0 recent articles, skipped LLM |
| vinu-tools (features) | ⚠️ | 0s | Request submitted (async) |
| vinu-initial-analysis | ✅ (after SQLite fix) | 31s | All 16 angles completed |
| vinu-strategy | ✅ | 2s | JPM weight=0.25 |
| vinu-simulator | ✅ | 5s | Sharpe=1.86, Return=9.3% |
| vinu-research | ❌ | 15s | 0 iterations — blocked by bugs 2.1–2.4 |

---

## Additional fix (applied before Phase 1)

### SQLite thread-safety in initial-analysis

`vinu-initial-analysis/vinu_initial_analysis/storage/meta.py:34` — changed
`sqlite3.connect()` to `sqlite3.connect(check_same_thread=False)`.
Rebuilt container. All 16 angles now complete instead of crashing on the
SQLite threading check.

### Empty articles guard in pipeline

`run_pipeline.py` `step_news` — added guard for empty `targets` list before
`ThreadPoolExecutor(max_workers=min(5, len(targets)))` which crashes with 0 workers.
