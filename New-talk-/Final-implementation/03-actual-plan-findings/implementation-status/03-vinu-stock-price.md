---
name: implementation-status-vinu-stock-price
status: in-progress
purpose: tracks real code changes made to vinu-stock-price against 03-storage-design.md's naming/root rules and layout.
---

# vinu-stock-price — Implementation Status

## What's built

- **Required data root**: `vinu_stock/config.py` now calls
  `require_data_root("STOCK")` instead of falling back to
  `Path.cwd()/"data"`. `VINU_STOCK_META_DB_PATH` (the old override var)
  is gone — meta db path is now always
  `{VINU_STOCK_DATA_ROOT}/vinu_stock_price.db`.
- **DB renamed**: `meta.db` → `vinu_stock_price.db` (code-level; no real
  data affected — see "Not yet done" below, there was none to begin
  with).
- `.env` created at `vinu-stock-price/.env` (gitignored) with
  `VINU_STOCK_DATA_ROOT=./data` — preserves today's actual behavior,
  now explicit.
- `.env-example` updated: `VINU_STOCK_META_DB_PATH=/data/meta.db` line
  removed (now derived from `VINU_STOCK_DATA_ROOT`, not a separate var).
- `tests/test_api.py`'s fixture cleaned up — it set the now-dead
  `VINU_STOCK_META_DB_PATH` env var; removed since it's a no-op and
  could mislead a future reader into thinking it still does something.

## Tested

```
33 passed, 0 failed
```

Full suite, system Python (same stale-`.venv` situation as vinu-news —
`pip show vinu-stock-price` inside `vinu-stock-price/.venv` also points
at a path that no longer matches the current repo layout; used system
Python instead).

## Correction to the original build-status audit

`04-build-status.md` claimed the live-file naming was flat
`{year}.parquet` with no daily sharding. On closer read of
`storage/parquet.py` and `backfill/orchestrator.py`, that's incomplete:
**daily sharding already exists and already works**, just not visible
from `storage/paths.py` alone (`live_year_path()` only names the
*consolidated* base file):

- `parquet.append_bars()` writes each new batch to
  `{stem}_{YYYYMMDD}.parquet` — a fresh shard per day, exactly the
  `{year}_{YYYYMMDD}.parquet` shape the storage design called for.
- `parquet.read_bars()` transparently merges the base file + all its
  daily shards at read time, deduped by `(symbol, provider, bar_ts)`.
- `orchestrator.rollover_and_consolidate()` does real, wired-in
  maintenance: consolidates the current year's shards into the base file
  once shard count crosses `SHARD_CONSOLIDATION_THRESHOLD`, and rolls
  fully-past years from `live/` into `archive/` (single `{year}.parquet`).
- Test coverage: `tests/test_parquet_io.py::test_write_and_read_dedupe`
  exercises the shard-write + merged-read path end-to-end (passing).
  `consolidate_live_shards()` itself has no direct test — a real gap,
  flagged but not fixed given the size of what's still queued elsewhere.

**Conclusion: Phase 2 (live daily-shard naming) needed no code changes —
it was already correctly built.** This is a correction to
`04-build-status.md`, not new work.

## Deliberately not done: `ParquetStore` adoption

Evaluated and decided against, not merely deferred. The bespoke code in
`storage/parquet.py` does more than `vinu_infra.parquet.ParquetStore`
offers out of the box (day-sharding, threshold-based consolidation,
year-rollover, composite-key dedup tuned to `(symbol, provider, bar_ts)`)
and is already correct and tested. Routing it through `ParquetStore`
would mean either reimplementing all of that on top of the generic store
or stripping it down to `ParquetStore`'s simpler shape — pure churn for
a component that isn't broken. Reusing `ParquetStore` stays the default
for new storage code (per `03-storage-design.md` rule #2); it isn't
being retrofitted onto working code that doesn't need it.

## Phase 6a: API redesign — done

New file `vinu_stock/server/routes_v1.py`, mounted additively at
`/v1/stage1/vinu-stock-price/*` alongside the existing `/stock/*` routes
(which stay — health/catalog/watchlist/settings/global-backfill are
operational routes outside the per-ticker fetch/trigger shape).

- `GET /v1/stage1/vinu-stock-price/fetch/{ticker}/{granularity}/{time-range}[?page=]`
  — reads stored candles, resampled to the requested granularity via the
  existing query engine. `200` with the 5-field envelope
  (`run_id: null`, `status: "ok"`, `computed_at`, `tier: "tier1"`,
  `data`) if found, `404`/`status: "not_found"` if not — matches
  `02-api-design.md`'s "fetch never auto-triggers" rule. Pagination:
  `page` query param, 500 rows/page per the resolved spec item.
- `POST /v1/stage1/vinu-stock-price/trigger/{ticker}/{granularity}/{time-range}`
  — `202`, assigns a `run_id`, kicks off `StockService.run_backfill()`
  for that one ticker in a background thread (reusing the existing
  backfill pipeline, not new ingest logic).
- `GET .../fetch/{ticker}/{granularity}/{time-range}/{run_id}` — polls a
  trigger's status: `202`/`computing` while running, falls through to a
  normal fetch once done, `404` for an unknown run_id.

**Judgment calls, documented in the file's module docstring:**
- `tier` is always `"tier1"` for this component (raw append-only price
  data) — a natural extension of the storage-plan's tier naming, not a
  new concept; the envelope's tier field was designed around
  tier2/tier3 for vinu-initial-analysis's angle runs, which doesn't
  apply to raw data.
- `trigger`'s `{granularity}` is validated but doesn't change what gets
  fetched — ingestion always pulls 1m raw per the "fetch only 1min,
  resample the rest" rule; resampling happens at `fetch` time.
- Job tracking for `trigger` is an in-memory dict, matching this exact
  component's existing `/backfill/trigger`/`/ingest/trigger` convention
  (`routes_config.py`) — not the SQL-run-log pattern from
  `03-storage-design.md` section 7, which targets a different problem
  (resolving "latest angle run" for vinu-initial-analysis). This is a
  raw ingest trigger, not an analysis run.

Tested: `tests/test_api_v1.py` (7 new tests — fetch hit/miss/resample,
bad granularity/time-range validation, trigger→poll flow with
`StockService.run_backfill` mocked out to avoid a real provider call).
Full suite: **40 passed, 0 failed** (33 prior + 7 new).

## Not yet done

Nothing else queued for this component specifically — Phase 2 and Phase
6 are both done. Any future work here would come from cross-component
needs (e.g. if Phase 5's price-dependent methods need a data shape this
component doesn't yet expose).
