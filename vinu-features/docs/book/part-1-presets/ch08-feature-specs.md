# Chapter 8 — Structured Feature Specs

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/compute/feature_spec.py` |

## Two input styles

Both normalize to resolved column names (e.g. `rsi_20`) before compute and storage.

| Style | CLI | HTTP |
|-------|-----|------|
| Legacy | `--features rsi_14,sma_20` | `"features": ["rsi_14"]` |
| Structured | `--feature rsi:period=20` | `"features": [{"kind":"rsi","params":{"period":20}}]` |

## Discoverability

```bash
vinu-features features list
vinu-features features help rsi
```

HTTP: `GET /features`, `GET /features/{kind}`

Catalog: [`feature_catalog.py`](../../../vinu_features/compute/feature_catalog.py)
