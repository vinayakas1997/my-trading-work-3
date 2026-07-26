# Task 1: Book/Artifact Link

**Status:** DONE

## Purpose

Give a closed `Position` a way to identify which Phase 4 `TradePlan` artifact opened it, and a
way to mark it as already fed back upstream — the prerequisite for everything else in this
phase, since without it nothing can know which forecast to score.

## Approach

- `Position.artifact_id: str = ""` (schema.py); `artifact_id`/`feedback_processed_at` columns
  added to `open_positions`/`closed_positions` via `BookBackend.MIGRATIONS`
  (`SCHEMA_VERSION` 1→2), the same `PRAGMA user_version`-gated migration mechanism
  `SQLiteBackend` already provides (unused by this file until now — it previously relied on
  `CREATE TABLE IF NOT EXISTS` alone, which can't add columns to an existing table).
- `open_position(..., artifact_id: str = "")`; `_close_position` carries `pos.artifact_id`
  forward into the closed-positions row.
- `list_closed_positions(backend, symbol=None, unprocessed_only=False) -> list[dict]`: plain
  dicts (not the `Position` dataclass) since closed rows carry `close_price`, which the
  open-position dataclass has no field for. `unprocessed_only` filters on
  `feedback_processed_at IS NULL AND artifact_id != ''` — positions with no artifact (opened
  outside the Phase 6 orchestrator) are never candidates for feedback.
- `mark_feedback_processed(backend, position_id)`.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/book/schema.py` | — | Added `Position.artifact_id` |
| `vinu_live/book/positions.py` | — | Migration, `open_position`/`_close_position` threading, `list_closed_positions`, `mark_feedback_processed` |
| `vinu_live/book/__init__.py` | — | Exported the two new functions |
| `vinu_live/trade_plan/orchestrator.py` | `_maybe_enter` | Passes `plan["_artifact_id"]` into `open_position` |

## Verification

- [x] Tests pass (`tests/test_book.py`'s new `TestArtifactIdAndFeedback` class, 5 tests; full `test_book.py` 22 tests)
- [x] Migration verified non-destructive against the pre-existing schema (existing `test_book.py`/`test_breaker.py`/`test_trade_plan_orchestrator.py` tests — which create fresh DBs through the same migration path — all still pass unmodified)
- [x] No runtime LLM call introduced outside `vinu-research`
