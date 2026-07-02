# Chapter 2 — Concepts Glossary

| Field | Value |
|-------|-------|
| **Package** | vinu-features |
| **Status** | v1 |

## Terms

| Term | Meaning |
|------|---------|
| **Preset** | Blueprint listing indicator column names |
| **Request** | One user job row in SQLite |
| **Run folder** | `{id}_{slug}/` with manifest + parquet |
| **Warm-up** | Extra OHLCV bars before `from_ts` for SMA/RSI |
| **Dedup hash** | SHA256 of symbols+dates+features; returns existing done run |

## Status values

`pending` → `running` → `done` | `failed` | `deleted`
