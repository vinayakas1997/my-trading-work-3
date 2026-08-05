# Task 1: Position Schema and CRUD

**Status:** IN PROGRESS

## Purpose

Implement the position schema, database backend, and CRUD operations for the live book ledger.

## Approach

- Use `vinu_infra.sqlite.SQLiteBackend` for storage
- Position fields: symbol, side, qty, avg_entry, realized_pnl, unrealized_pnl, stop_loss, take_profit, opened_at, updated_at
- CRUD: open_position, add_to_position, reduce_position, close_position, get_position, list_open_positions

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/book/schema.py` | — | Created |
| `vinu_live/book/positions.py` | — | Created |

## Verification

- [x] Opening, adding to, reducing, closing positions produce correct state
- [x] Concurrency-safe: near-simultaneous fills resolve correctly
