# Chapter 5 — Request Lifecycle

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Module** | `vinu_features/service.py` |
| **Status** | v1 |
| **Prerequisites** | ch03 |

## Flow

```mermaid
stateDiagram-v2
  [*] --> pending: submit
  pending --> running: worker_claim
  running --> done: parquet_written
  running --> failed: exception
  done --> deleted: delete_api
```

## Dedup

Identical symbols, dates, interval, and features return an existing `done` row instead of creating duplicate work.
