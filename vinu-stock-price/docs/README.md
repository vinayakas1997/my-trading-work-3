# Stock Price System Documentation

Documentation for the **vinu-stock-price** OHLCV archive, live ingest, and query API.

| Guide | Description |
|-------|-------------|
| [**Complete Guide — Stock Price**](complete_guide_stock_price.md) | Full architecture: Parquet layout, providers, backfill/live flows, API, Docker, tests |
| [**How to Use**](../how-to/README.md) | Install, backfill, live ingest, CLI/API examples, troubleshooting |

**Quick start:**

```bash
cd vinu-stock-price
pip install -e ".[dev]"
vinu-stock-query watchlist AAPL
vinu-stock-backfill AAPL --from-year 2024 --to-year 2024
pytest tests/ -v
```

**Data root:** `VINU_STOCK_DATA_ROOT` (default `./data`) — `meta.db` + `prices/1m/{SYMBOL}/`
