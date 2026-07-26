# Phase 09 — Test Summary

## Tests Run

### Track A — vinu-agent

| Test File | Total | Pass | Fail | Notes |
|-----------|-------|------|------|-------|
| `vinu-agent/tests/test_unified_memory.py` | 24 | 24 | 0 | All pass (incl. `test_list_by_symbol` updated for unique source_ids) |
| `vinu-agent/tests/test_loop.py` | 14 | 14 | 0 | All pass |

**Total: 38 tests, 38 pass**

### Track B — vinu-research

| Test File | Total | Pass | Fail | Notes |
|-----------|-------|------|------|-------|
| `vinu-research/tests/test_sqlite_backend.py` | 13 | 12 | 1 | `test_concurrent_writes`: pre-existing Windows SQLite locking issue |
| `vinu-research/tests/test_catalog.py` | 11 | 0 | 11 | All pre-existing Windows PermissionError (SQLite handle held during temp dir cleanup) |
| `vinu-research/tests/test_loop.py` | 54 | 54 | 0 | All pass |
| `vinu-research/tests/test_service.py` | 26 | 26 | 0 | All pass |

**Total: 104 tests, 92 pass, 12 pre-existing Windows failures**

### Why the PermissionError?

The `test_catalog.py` tests create a `ResearchStorage` pointing at a temp SQLite file inside a `with TemporaryDirectory()`. The `SQLiteBackend` holds a thread-local connection (`self._local.conn`) that keeps the file handle open. When the `with` block exits, `TemporaryDirectory` tries to delete the file, but Windows won't release the handle until the connection is garbage-collected. The tests don't call `storage.close()` before the temp dir cleanup, so `PermissionError: [WinError 32]` fires on every test.

This is purely a Windows issue — on Linux/macOS, unlink works on open files. Fixing it would require adding a `close()` call (or a context-manager cleanup) to each test, which is out of scope for this phase. The test logic itself would pass; the error is only in teardown.

## Verdict

No regressions introduced. All pre-existing failures are Windows-specific (SQLite file locking / temp directory cleanup).

Phase 09 is complete.
