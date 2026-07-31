---
name: vinu-tools
container: features-api
port: 8082
depends_on: [vinu-stock-price]
---

# vinu-tools (features-api)

## What it does

Computes technical/alpha features and ML model runs from stock-price OHLCV
data, exposed as preset "blueprints" plus an async job registry so feature
computation can run as a background request.

## Scope for this E2E plan

Computes the feature sets that `vinu-strategy` (medium-tier strategy) and
`vinu-research` (complex-tier strategy generation) need, across the full
2022-01-01 → 2026-06-30 window and whatever timeframe each strategy asks
for (1-day for most, potentially the shorter aggregates for anything
intraday).

## When it runs

Depends on `vinu-stock-price` (docker-compose `depends_on: stock-api`) —
must have price data cached first. Runs before `vinu-strategy` and
`vinu-research`, both of which call it for features rather than computing
their own.

## Where data is stored

- Computed features: Parquet under `VINU_FEATURES_DATA_DIR` (default
  `./data`), organized as `data/runs/{id}_{slug}/manifest.md` +
  `features.parquet` per job.
- Job/request registry: SQLite at `VINU_FEATURES_META_DB_PATH`
  (`meta.db`).

## Dependencies

- `VINU_STOCK_API_URL` (`vinu-stock-price`, port 8081) — fetches candles to
  compute features from.

## API surface used by this plan

- `GET /presets` — see what feature blueprints exist.
- `POST /requests` + `POST /requests/{id}/run` — kick off a feature
  computation job for a symbol/date-range.
- `GET /features/{symbol_or_kind}` — retrieve computed features for
  strategy evaluation.

## Known gap as of this document

No feature computation has been run yet — blocked on `vinu-stock-price`
having real cached data first.
