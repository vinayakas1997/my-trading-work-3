# Stock Price System Documentation

**Start at the textbook:** [**INDEX.md**](INDEX.md) — chapter-based guide for operators, researchers, and contributors.

| Guide | Description |
|-------|-------------|
| [**Textbook INDEX**](INDEX.md) | Master index: providers, storage, ingest, query, API |
| [**Complete Guide**](complete_guide_stock_price.md) | Legacy monolithic reference (redirect banner) |
| [**How to Use**](../how-to/README.md) | Practical quick reference |

**Quick start:**

```bash
cd vinu-stock-price
pip install -e ".[dev]"
vinu-stock-query watchlist AAPL
vinu-stock-backfill AAPL --from-year 2024 --to-year 2024
pytest tests/ -v
```

**Data root:** `VINU_STOCK_DATA_ROOT` (default `./data`) — `meta.db` + `prices/1m/{SYMBOL}/`
