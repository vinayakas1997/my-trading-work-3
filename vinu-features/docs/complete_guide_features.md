# Complete Guide — vinu-features

## Overview

`vinu-features` accepts feature run requests, tracks them in SQLite, computes indicators from `vinu-stock-price` OHLCV, and writes run artifacts:

```
data/runs/{id}_{slug}/
  manifest.md
  features.parquet
```

## Install

```bash
cd vinu-features
pip install -e ".[dev]"
cp .env.example .env
```

Ensure `vinu-stock-price` serves on `VINU_STOCK_API_URL` (default `:8081`).

## Workflow

1. **Submit** — create registry row (`pending`)
2. **Worker** — process pending jobs
3. **Query** — by title or id for `status` and `file_path`
4. **Delete** — remove folder and mark `deleted`

### CLI

```bash
vinu-features submit --title swing_aapl --symbols AAPL --days 365 --preset swing_basic
vinu-features worker --once
vinu-features status --title swing_aapl
vinu-features list --status done
vinu-features delete --id 1
vinu-features serve
```

### HTTP

| Method | Path |
|--------|------|
| POST | `/requests` |
| GET | `/requests/by-title/{title}` |
| POST | `/requests/{id}/run` |
| DELETE | `/requests/{id}` |
| GET | `/presets` |
| GET | `/features` |
| GET | `/features/{kind}` |

## Feature specs

Legacy names still work (`rsi_14`, `sma_20`). Structured specs add flexibility:

```bash
vinu-features submit --title custom --symbols AAPL --feature rsi:period=20 --feature sma:period=50
vinu-features features list
vinu-features features help rsi
```

HTTP:

```json
{
  "title": "custom",
  "symbols": ["AAPL"],
  "features": ["sma_20", {"kind": "rsi", "params": {"period": 20}}]
}
```

Custom indicators: `sma_100`, `rsi_14`, or `rsi:period=20` → column `rsi_20`.

| Name | Description |
|------|-------------|
| `basic_ta`, `swing_basic`, `momentum` | TA bundles |
| `trend_pack`, `volatility_pack`, `volume_pack`, `mean_reversion_pack` | Themed packs |
| `full_ta` | All TA indicators |
| `alpha101`, `alpha158`, `alpha360` | Alpha factor sets (101 / 158 / 360 columns) |

Custom indicators: `sma_100`, `rsi_14`, etc.

## Compute layout

```text
vinu_features/compute/
  registry.py           # indicator dispatch
  indicators/           # rsi/, sma/, macd/, ...
  bigger_recipe/
    catalog.py          # recipe dispatch
    basic_ta/, swing_basic/, momentum/, …   # TA presets
    alpha101/, alpha158/, alpha360/         # alpha factor sets
  ml_models/
    registry.py         # model dispatch
    runner.py           # run_ml_step orchestration
    linear_regression/, ridge/, lightgbm/, …
  feature_catalog.py    # indicator metadata + help
  feature_spec.py       # parse/validate structured specs
```

ML extras: `pip install -e ".[ml]"` — optional `ml_model` + `ml_label` on submit.

## Book

See [docs/book/ARCHITECTURE.md](book/ARCHITECTURE.md) for chapter index.
