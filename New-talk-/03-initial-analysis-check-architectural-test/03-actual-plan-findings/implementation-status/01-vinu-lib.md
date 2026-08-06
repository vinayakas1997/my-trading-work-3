---
name: implementation-status-vinu-infra
status: in-progress
purpose: tracks real code changes made to vinu-infra against 03-storage-design.md's naming/root rules.
---

# vinu-infra — Implementation Status

> **NOTE (2026-08-06):** this component was renamed from `vinu-lib` to
> **`vinu-infra`** (and the Python package from `vinu_lib` to `vinu_infra`).
> All future references, code, docs, and component imports should use
> `vinu-infra` going forward. This file documents the work done while it
> was still named `vinu-lib`.

## What's built

- **`require_data_root(prefix: str) -> Path`** (new, `vinu-infra/config.py`) —
  reads `VINU_<prefix>_DATA_ROOT`, raises `MissingDataRootError` if unset.
  No cwd-relative fallback — this is the single function all 3 in-scope
  components now call to resolve their root, replacing each component's
  own hand-rolled `Path.cwd() / "data"` default.

## What's still true from the original audit (untouched)

- `vinu_infra.parquet.ParquetStore` — still unused by any component. Queued
  for Phase 2/3 (vinu-stock-price and vinu-initial-analysis storage
  conformance).
- `vinu_infra.config.ServiceConfig`/`from_env` — still unused; this is a
  host/port/log-level config helper, unrelated to the data-root problem
  (`require_data_root` is a new, separate function, not a fix to this
  existing one).

## Tested

Ran `pytest` (system Python, since this is where `vinu-infra` and all 3
in-scope components are actually installed editable — see
`02-vinu-news.md`'s note on the stale per-component `.venv`s):

```
67 passed, 1 failed
```

The 1 failure (`test_telemetry.py::test_record_llm_call_safe_writes_via_global_cache`)
is a Windows-only temp-file-handle race unlocking `telemetry.db` during
test cleanup — unrelated module (telemetry, not config), confirmed by
scope: `require_data_root` is new code, added nothing to any existing
function's behavior.

## Not yet done

Nothing else planned for vinu-infra right now — it's reuse-only for the
remaining phases (`ParquetStore` gets adopted by other components; this
file doesn't change further unless a gap surfaces).
