# vinu-features

Preset blueprints, SQLite job registry, and OOM-safe feature run artifacts from `vinu-stock-price` OHLCV.

## Quick start

```bash
cd vinu-features
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"

cp .env.example .env
# Ensure vinu-stock-price is running on :8081

vinu-features submit --title swing_aapl --symbols AAPL --days 365 --preset swing_basic
vinu-features worker --once
vinu-features status --title swing_aapl
```

## HTTP API

```bash
vinu-features serve
# POST http://127.0.0.1:8082/requests
# GET  http://127.0.0.1:8082/requests/by-title/swing_aapl
```

## Output layout

Each completed run writes:

```
data/runs/{id}_{slug}/
  manifest.md       # request audit trail
  features.parquet  # ts, symbol, OHLCV, indicator columns
```

Registry state lives in SQLite (`VINU_FEATURES_META_DB_PATH`).

## Docs

- [Complete guide](docs/complete_guide_features.md)
- [Book index](docs/book/ARCHITECTURE.md)

## Depends on

- [vinu-stock-price](../vinu-stock-price/) — `GET /candles/{symbol}` for OHLCV
