# Phase 07: Unified Agent-Memory Layer

**Status:** COMPLETED
**Started:** 2026-07-26
**Depends on:** Step 5 (stock-price & news migration) — done; Step 2 (catalog) — done
**Blocks:** Step 9 (context-efficient retrieval)

## What It Delivers

A cross-package memory catalog that aggregates price data, news analysis, research iterations, simulation runs, and agent findings into a unified queryable store. The agent gets a single `query_memory` tool and automatic symbol-relevant context injection in the system prompt — replacing the ad-hoc file-based `PersistentMemory` with a structured, multi-source memory layer.

## Architecture

```
vinu-agent memory layer
│
├── UnifiedMemoryStore       (SQLite + FTS5 — local cache of all service data)
│   ├── memory_entries table (unified rows with source, symbol, type, content, embedding keywords)
│   └── sync_watermarks    (tracks last-sync time per source)
│
├── SyncService              (HTTP pulls from each upstream service)
│   ├── sync_research()      → GET /research/runs, /research/artifacts
│   ├── sync_simulator()     → GET /runs
│   ├── sync_news()          → GET /search
│   └── sync_stock_price()   → GET /candles/{symbol}
│
├── query_memory tool        (agent-callable — searches all sources)
│
└── Context injection        (automatic — symbol-relevant entries in system prompt)
```

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-agent/vinu_agent/memory/unified_store.py` | vinu-agent | create |
| `vinu-agent/vinu_agent/memory/sync_service.py` | vinu-agent | create |
| `vinu-agent/vinu_agent/memory/query_engine.py` | vinu-agent | create |
| `vinu-agent/vinu_agent/memory/__init__.py` | vinu-agent | modify |
| `vinu-agent/vinu_agent/tools/__init__.py` | vinu-agent | modify (auto-discovers new tool) |
| `vinu-agent/vinu_agent/agent/context.py` | vinu-agent | modify |
| `vinu-agent/vinu_agent/service.py` | vinu-agent | modify |
| `vinu-agent/vinu_agent/tools/remember_tool.py` | vinu-agent | modify (route through unified store) |
| `vinu-agent/vinu_agent/memory/persistent.py` | vinu-agent | deprecate (superseded by unified store) |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-store-schema.md` | Build UnifiedMemoryStore (SQLite schema, CRUD, FTS5, upsert) | DONE |
| 2 | `02-task-sync-service.md` | Build SyncService with HTTP pulls from all upstream services | DONE |
| 3 | `03-task-query-tool.md` | Create query_memory agent tool | DONE |
| 4 | `04-task-context-wiring.md` | Wire unified memory into agent context builder + deprecate PersistentMemory | DONE |

## Dependencies Met

- [x] Step 5 completed — MetaBackend and NewsRepository extend SQLiteBackend
- [x] Step 2 completed — catalog tables with lifetime_trial_count and best_sharpe_ever
- [x] All upstream services expose HTTP endpoints the sync layer can call
