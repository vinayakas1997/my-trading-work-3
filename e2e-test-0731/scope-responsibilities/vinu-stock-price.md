---
name: vinu-stock-price
port: 8081
depends_on: []
---

# vinu-stock-price

## What it does

Historical and live OHLCV candle storage and query API. This is the root
data source every other component ultimately depends on — nothing upstream
of it in the dependency chain.

## Scope for this E2E plan

Fetches real 1-minute candles from Alpaca for the ticker list, for
2022-01-01 → 2026-06-30, and serves the 1-day/4-hour/1-hour/15-minute
aggregates derived from that 1-minute base. This is the first real work item
in Stage 1 — no simulation or strategy evaluation can start until this
component has the data cached.

## When it runs

Standalone service, no upstream dependency — can start first, before any
other vinu-* service. Under Docker it's `stock-api` on port 8081 with no
`depends_on` entries. In this E2E plan it needs to run (or be run once for a
backfill, then serve from cache) before `vinu-tools`, `vinu-initial-analysis`,
`vinu-strategy`, `vinu-simulator`, `vinu-portfolio`, `vinu-research`, and
`vinu-live` can do anything meaningful, since all of them call it for price
data.

## Where data is stored

- Candle data: Parquet files under `VINU_STOCK_DATA_ROOT` (default `./data`).
- Catalog/metadata: SQLite at `VINU_STOCK_META_DB_PATH` (default
  `./data/meta.db`) — tracks which symbol/interval/date-range combinations
  are already cached.

## Providers

Configurable via `VINU_STOCK_DEFAULT_PROVIDER` — supports Polygon, Alpaca,
and Yahoo (fallback chain). This plan uses **Alpaca** exclusively, since
that's the credential already verified working this session.

## API surface used by this plan

- `GET /candles/{symbol}` with `interval`, `from`/`to` or `days`, `provider`
  — the endpoint every downstream service and the historical-simulation CLI
  hits.
- `GET /catalog/{symbol}` — to check what's already cached before
  re-fetching.

## Known gap as of this document

No 1-minute (or any) candle data currently exists locally in this
environment. This is the first thing that has to happen before anything
else in Stage 1 can run for real.
