---
name: storage-design
status: discussion-phase
purpose: the redesigned storage layout for vinu-news, vinu-stock-price, and vinu-initial-analysis — replacing the inconsistent, immutability-violating storage found in the real implementation (see the exploration findings referenced below). Not a patch on existing data; a clean redesign, existing data disregarded per the decision to properly re-implement.
---

# Storage Design — vinu-news, vinu-stock-price, vinu-initial-analysis

## Why this redesign happened

An exploration of the real implementation (`vinu-components/`) found: two
disconnected data roots (Docker vs. local dev default), five different
Parquet partitioning schemes across components with no shared convention,
three components independently naming their SQLite file `meta.db`, no
shared env-var convention, and — most importantly — `vinu-initial-analysis`
**pruning old runs after 10**, which directly violates
`../../00-project-understanding/02-storage-plan.md`'s core principle that
closed periods must be immutable. This file is the clean redesign, not a
patch — existing data is disregarded per the decision to properly
re-implement rather than migrate.

## 1. One data root, no silent default

Every component requires `VINU_<SERVICE>_DATA_ROOT` to be explicitly set —
**no `cwd`-relative fallback**. If it's not set, the service fails to
start. This is what eliminates the two-disconnected-roots problem at the
source: there's no ambiguous default left to diverge from.

## 2. Consistent naming — everywhere

- **Env vars**: always `VINU_<SERVICE>_DATA_ROOT` — no `_DATA_DIR`/`_DB_PATH`
  variants.
- **SQLite files**: always component-prefixed — `vinu_news.db`,
  `vinu_stock_price.db`, `vinu_initial_analysis_runs.db`. Never a generic
  `meta.db`.
- **Shared library reuse**: all components route through
  `vinu_lib.parquet.ParquetStore` and `vinu_lib.sqlite.SQLiteBackend`
  instead of each reimplementing its own read/write/dedup logic.

## 3. Raw data — fetch at the finest granularity, resample the rest

Only `1min` bars are fetched from Alpaca directly. `5min`, `15min`, `1hr`,
`4hr`, `1day` are all resampled/derived from the `1min` base — never
independently fetched. This is a one-directional rule: fine data can
always be aggregated up into coarse bars, but coarse data can never be
split back down into fine bars, so `1min` is the only granularity that has
to touch the data source. (Resampling itself is already implemented — not
redesigned here.)

## 4. `vinu-stock-price` layout (Tier 1 — raw, append-only, never pruned)

```
{ticker}/{granularity}/archive/{year}.parquet
{ticker}/{granularity}/live/{year}_{YYYYMMDD}.parquet   ← today's shard, pre-consolidation
```

Daily shards absorb new bars cheaply (append-only, small file); a
consolidation step periodically merges finished shards into the year
file. This avoids rewriting an entire year's Parquet file on every new
bar — the naive `{ticker}/{granularity}/{year}.parquet`-only version
would have to read-modify-write the whole year file per append, which
doesn't scale at `1min` granularity.

## 5. `vinu-news` layout (Tier 1 — raw, relational)

Stays SQLite — articles/mentions/threads/full-text-search don't fit a
columnar Parquet shape well, and this part of the current design is
already sound. Only change: rename the file to `vinu_news.db` and apply
the same required-env-var root rule as everything else.

## 6. `vinu-initial-analysis` layout (Tier 2/3 — the fix for the immutability bug)

**Single-ticker methods:**
```
{ticker}/{method}/{granularity}/{tier}/{run_id}.parquet
AAPL/kronos/1hr/tier2/run_8f3a2b.parquet
AAPL/kronos/1hr/tier3/run_c1d9e0.parquet
```

**Multi-ticker methods** (iTransformer, MOIRAI, FinMamba, the
cross-attention+GCN fusion — methods whose API calls take a
comma-separated `{ticker}` list): a separate branch, since a joint
multi-ticker result isn't any single ticker's data and can't be dropped
into one ticker's folder without corrupting single-ticker lookups:
```
_multi/{sorted-ticker-list-hash}/{method}/{granularity}/{tier}/{run_id}.parquet
```

**Why each segment is there:**
- `{ticker}` first — matches the API's primary lookup key, and matches
  the storage-plan's cross-ticker comparability goal.
- `{method}` — one of the 32 methods from `01-present-considerations/`.
- `{granularity}` — a 1hr Kronos run and a 1day Kronos run are different
  results; without this segment they'd collide in the same folder with
  nothing but an opaque `run_id` telling them apart.
- `{tier}` — `tier2` (quarterly, scheduled) is **never pruned** — this is
  what actually *enforces* immutability of closed periods, not just
  states it as a principle. `tier3` (triggered) is explicitly not the
  official quarterly record, so it's fine to prune on a retention
  schedule (e.g. 90 days) — and because it's a separate folder from
  `tier2`, that pruning can never touch a frozen quarterly result.
- `{run_id}` — the exact same identifier returned in the API's `run_id`
  field (see `02-api-design.md`'s response envelope) and used in the
  `{run-id}` URL segment for polling. One ID, used identically in the API
  response, the URL, and the filename — full traceability with no
  separate ID scheme to reconcile.

## 7. Resolving "latest" — through SQL, never the filesystem

`vinu_initial_analysis_runs.db` (SQLite, component-prefixed per rule #2)
tracks every run:

```
runs(run_id PK, ticker, method, granularity, tier,
     time_range_start, time_range_end,
     status,        -- computing | ok | failed
     computed_at, file_path)
```

When `fetch` is called **without** a `{run-id}` (a plain
ticker/method/granularity/time-range lookup), it resolves "latest" via:
```sql
SELECT file_path FROM runs
WHERE ticker=? AND method=? AND granularity=? AND tier=?
  AND status='ok'
ORDER BY computed_at DESC LIMIT 1
```

**Never by scanning the folder and picking the newest file by `mtime`.**
The real implementation's existing code does exactly that today, and a
comment in that code already documents a double-counting bug it caused —
this redesign removes that failure mode entirely by making the SQL run-log
the single source of truth for "which run is current."

## Related files

- `02-api-design.md` — the API this storage layout backs; `run_id`,
  `tier`, and the `fetch`/`trigger`/`404`/`202` behavior all map directly
  onto what's described here
- `../limitations_and_other_info.md` — Alpaca-only, fixed `2022-01-01`
  start + quarterly cadence, the constraints this design was built against
- `../../00-project-understanding/02-storage-plan.md` — the original
  5-tier concept and the immutability principle this redesign enforces in
  code, not just states
