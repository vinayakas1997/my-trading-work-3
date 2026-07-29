# S-03: Batch Evidence Writes — Explanation & Status

## What It Is

Replaces per-item disk writes with a single batch write per research iteration, reducing I/O overhead and serialization churn.

## Components

1. **`add_evidence_batch()` in `hypothesis_registry.py`** — accepts `list[Evidence]`, appends all items to the in-memory registry, then triggers a single `_save()` call. Avoids N separate serialize-write cycles.

2. **`loop.py` batch collection** — the research loop gathers all evidence for an iteration into a list and calls `add_evidence_batch()` once, replacing the previous pattern of calling `add_evidence()` per item.

3. **Known limitation: no file locking** — the implementation uses temp-file + `os.replace` for atomic single-writer semantics. Concurrent multi-process writes can still race on `_load()`. This is acceptable for serial test plans where only one process writes at a time.

## Current Status: ✅ IMPLEMENTED

All evidence in a research iteration is flushed in one write.
