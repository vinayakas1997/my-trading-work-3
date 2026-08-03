---
name: hypothesis-registry-home-dir-crash
status: fixed
severity: crashes-every-real-research-run
---

# Bug: `HypothesisRegistry()`'s default path used `Path.home()`, which doesn't exist in `research-api`'s read-only container

## What was wrong

After fixing the null-`user_idea` crash
([`research-run-null-user-idea-crash.md`](research-run-null-user-idea-crash.md)),
`POST /research/run` failed again, for all 3 tickers, with:

```
{"detail":"[Errno 30] Read-only file system: '/nonexistent'"}
```

Traceback showed `service.py:146`'s `HypothesisRegistry()` (constructed
with **no path argument**) crashing inside its own constructor
(`hypothesis_registry.py:22`, `self._path.parent.mkdir(...)`).

Root cause: `hypothesis_registry.py`'s module-level default,
`HYPOTHESES_DIR = Path.home() / ".vinu"`, completely ignores
`ResearchConfig.data_root` (already correctly `/data` in this container,
per
[`data-root-docker-path-mismatch.md`](data-root-docker-path-mismatch.md)).
`research-api`'s container is `read_only: true` with only `/data`
bind-mounted and writable; the container's user has no real home
directory entry, so `Path.home()` resolves to `/nonexistent` — this
exact class of bug already documented once for `vinu-agent`
(`VINU_AGENT_DATA_ROOT`'s comment in `.env-example`), just not yet
applied here.

Grepping confirmed this default is used from **11 separate call sites**
across the codebase — `service.py` (×2), `routes_hypothesis.py` (×2),
`routes_introspect.py` (×2), `tools.py` (×4), `cli.py` (×2) — every one of
them constructs `HypothesisRegistry()` with no explicit path, relying on
the same broken module-level default.

## Why it mattered

This is the storage backing the structured decision journal
(`implementation-plan-from-04/vinu-agent/plan.md`'s Piece 2 explicitly
reuses this exact class) — every real, non-`dry_run` research call
crashed here, for every symbol, unconditionally. `dry_run: true` calls
never reached this code path, so any earlier smoke-testing that only used
`dry_run` would never have caught it.

## What was fixed

Fixed the shared default in one place rather than touching all 11 call
sites: `hypothesis_registry.py`'s module-level `HYPOTHESES_DIR` now checks
`VINU_RESEARCH_DATA_ROOT` (the same env var `vinu_research/config.py`
already reads for its own data root) first, falling back to
`Path.home()/".vinu"` only when that var isn't set — preserving the
original behavior for host-mode (non-Docker) use. All 11 call sites
inherit the fix automatically since they all default through the same
`HYPOTHESES_PATH` constant.

`tests/test_hypothesis_registry.py` (23 tests) re-run, all passing —
none of them exercise the module-level default path directly (they all
pass an explicit `path=` in the fixture), so this fix didn't require new
test coverage to validate against regressions, just confirmation the
existing behavior is untouched.

## What was achieved

`POST /research/run` (and every other of the 11 call sites — the CLI,
the introspection routes, `tools.py`'s hypothesis-query tool used by
`vinu-agent`) now constructs its default `HypothesisRegistry` at `/data`
in Docker instead of crashing on a non-existent home directory. Confirmed
in production: all 3 tickers' real (non-dry-run) research runs completed
end to end immediately after this fix and the rebuild, each producing a
real backtest report and optimized strategy code.
