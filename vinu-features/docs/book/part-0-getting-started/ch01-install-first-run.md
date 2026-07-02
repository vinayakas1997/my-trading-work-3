# Chapter 1 — Install and First Run

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/cli.py` |
| **Status** | v1 |
| **Prerequisites** | ch00 |

## Learning objectives

- Install the package and configure `.env`.
- Submit a run and process it with the worker.

## Steps

```bash
pip install -e ".[dev]"
cp .env.example .env
vinu-stock-serve   # in vinu-stock-price, port 8081
vinu-features submit --title demo --symbols AAPL --days 90 --preset basic_ta --run
vinu-features status --title demo
```

Expected: `status=done`, `file_path` pointing to `data/runs/{id}_demo/`.
