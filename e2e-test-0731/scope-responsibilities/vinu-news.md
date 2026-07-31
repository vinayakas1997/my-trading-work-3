---
name: vinu-news
port: 8080
depends_on: [vinu-stock-price]
---

# vinu-news

## What it does

Financial news ingestion, tiered enrichment/LLM analysis, and querying,
driven off a configurable watchlist.

## Scope for this E2E plan

Best-effort historical news coverage for the same ticker list and
2022-01-01 → 2026-06-30 window used everywhere else. Feeds
`vinu-initial-analysis`'s correlation/impact work. This component's Alpaca
news coverage depth for older dates is unverified — it may not go back as
far as the price data does; that's a real open risk for this plan, not
assumed to work.

## When it runs

Independent of price data being cached (no hard `depends_on` in
docker-compose, though it calls `vinu-stock-price` for price-reaction
context on articles). Can run in parallel with the `vinu-stock-price`
backfill. Needs to be running before `vinu-initial-analysis` does anything
useful, since that service consumes news data directly.

## Where data is stored

SQLite at `VINU_NEWS_DB_PATH` (default `./data/news.db`).

## Providers

FMP and Alpaca (keys configured for news sourcing). This plan uses Alpaca's
news endpoint (`https://data.alpaca.markets/v1beta1`), already verified
reachable this session.

## Dependencies

- `VINU_STOCK_API_URL` (`vinu-stock-price`, port 8081) — for price-reaction
  enrichment on articles.
- Local LLM via `VINU_LLM_BASE_URL` (default Ollama, `llama3.2`) — used for
  tiered analysis/enrichment of articles. If no local LLM is running, this
  step degrades or fails depending on `VINU_LLM_ANALYSIS_MODE`.

## API surface used by this plan

- `GET /ticker/{symbol}` / `GET /watchlist/news` — historical article
  retrieval per ticker.
- `GET /high-impact` — filtered subset for correlation work.

## Known gap as of this document

Historical news depth from Alpaca back to 2022-01-01 has not been checked —
only that the news endpoint is reachable and returns *current* data. This
needs verification before Stage 1 execution, not assumed.
