# Task 1: Build UnifiedMemoryStore

**Status:** DONE

## Purpose

Create the SQLite-backed storage layer for the unified agent-memory catalog. This replaces the file-based `PersistentMemory` with a structured multi-source store supporting FTS5 full-text search, per-source sync watermarks, and typed memory entries.

## Approach

- Extends `vinu_infra.sqlite.SQLiteBackend` (hardened in Phase 1) — inherits upsert, thread-local connections, WAL mode, schema migrations
- `memory_entries` table — unified schema across all sources (research, simulator, stock-price, news, agent)
- `memory_fts` virtual table — FTS5 with porter stemmer for full-text search
- `sync_watermarks` table — tracks last-sync cursor per upstream source
- `MemoryEntry` dataclass — typed representation with `to_dict()`/`from_row()` helpers
- Bulk operations for full rebuilds and per-source clears

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-agent/vinu_agent/memory/unified_store.py` | 1-218 | Created — UnifiedMemoryStore, MemoryEntry, SCHEMA, FTS, CRUD, search, watermarks |

## Verification

- [x] Schema creates on init — memory_entries, memory_fts, sync_watermarks, indexes
- [x] add_entry persists and syncs FTS
- [x] search with FTS MATCH returns ranked results
- [x] search with symbol/source/type filters works
- [x] Watermarks track per-source sync state
- [x] bulk_add and clear_and_rebuild work
