# Chapter 6 — Worker and OOM-Safe Load

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/worker/runner.py`, `engine/engine.py` |
| **Status** | v1 |
| **Prerequisites** | ch05 |

## Learning objectives

- Run `vinu-features worker --once` to drain pending queue.
- Understand per-symbol fetch and incremental parquet append.

## OOM strategy

1. Fetch one symbol at a time from vinu-stock-price.
2. Apply indicators in memory for that symbol only.
3. Append to `features.parquet` via PyArrow writer.
4. Discard in-memory rows before next symbol.

Warm-up window: `from_ts - warmup_bars * interval_seconds`.
