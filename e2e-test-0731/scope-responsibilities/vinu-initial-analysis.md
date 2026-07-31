---
name: vinu-initial-analysis
container: initial-analysis-api
port: 8083
depends_on: [vinu-news, vinu-stock-price]
---

# vinu-initial-analysis (correlation system)

## What it does

Multi-angle news/price correlation, causality, drawdown, and
PnL-attribution analytics per symbol — answers "did this news move this
price, and by how much."

## Scope for this E2E plan

Best-effort historical correlation/impact analysis for the ticker list and
2022-01-01 → 2026-06-30 window, contingent on how far back `vinu-news`
actually has article coverage (see
[vinu-news.md](vinu-news.md)'s open gap). This feeds context into
`vinu-strategy`'s medium-tier trend+volatility strategy and
`vinu-research`'s complex-tier generation, but is not itself replayed by
the historical simulator (per the Step 07 scope decision — only risk-parity
+ regime-alignment tilts are replayed; correlation/impact tilts have no
historical trail to reconstruct).

## When it runs

Depends on both `vinu-news` and `vinu-stock-price` (docker-compose
`depends_on: news-api, stock-api`). Runs after both of those have data,
before `vinu-strategy`.

## Where data is stored

- Angle/analysis outputs: Parquet under `VINU_INITIAL_ANALYSIS_DATA_ROOT`
  (default `./data`) via `AngleStorage`.
- Run log: SQLite `runs.db`.

## Dependencies

- `VINU_NEWS_API_URL` (`vinu-news`, port 8080)
- `VINU_STOCK_API_URL` (`vinu-stock-price`, port 8081)

## API surface used by this plan

- `POST /run/{ticker}` — trigger analysis for a symbol.
- `GET /correlation/{ticker}`, `GET /impact/{ticker}`, `GET /drawdown/{ticker}`
  — retrieve results.
- `GET /correlation/batch` — multi-symbol at once (relevant to the shock
  clustering fix built in Step 02 of the prior plan).

## Known gap as of this document

Nothing computed yet — blocked on both upstream services having real data
first, and on the open question of how far back Alpaca's news actually
covers.
