# ISSUE-001 — timer_timerxl real model fails to load (ROFS) due to leaked Windows HOME

- **Component:** `docker-compose.yml` (initial-analysis-api env) / `vinu-initial-analysis/vinu_initial_analysis/angles/timer_timerxl/compute.py:88-90`
- **Phase found:** 1 (unit suite) / time-eaters analysis
- **Severity:** HIGH

## Description
The real Timer model never loads in the container. `AutoModelForCausalLM.from_pretrained(..., trust_remote_code=True)` raises `OSError(30, 'Read-only file system')`, so the angle silently runs the statistical proxy (`model_backend: "fallback_proxy"`).

Root cause: `.env` leaks the Windows host `HOME=C:Usersvinay` into the container. transformers writes the fetched remote-code file to `$HOME/.cache/huggingface/modules/` → a nonexistent Windows path on a read-only rootfs → OSError 30.

## Steps to reproduce
1. `docker compose exec initial-analysis-api python /tmp/time_angle.py timer_timerxl 512 3`
2. Observe `backend: fallback_proxy`, reason `OSError(30, 'Read-only file system')`.

## Actual
`model_backend == "fallback_proxy"` in the container (real weights present in `/models`).

## Expected
`model_backend == "pretrained"`, checkpoint `thuml/timer-base-84m`.

## Impact
- `vinu-initial-analysis/tests/test_timer_timerxl.py:95-103` (`test_pretrained_backend_actually_loads_in_this_environment`) fails in the container.
- All Timer forecasts in production were proxy-based (silent degradation), not the real model.

## Suggested fix (APPLIED)
`docker-compose.yml` initial-analysis-api environment: add `HF_HOME: /home/app/.cache/huggingface` (tmpfs mount already exists). Verified: real model loads.

## Status
FIXED (compose change; verify full suite).

## Follow-up
The `.env` `HOME` leak affects any `trust_remote_code=True` model. Consider fixing at source (remove/replace HOME in `.env`).

## Evidence
- `time-eaters-analysis/timer_timerxl/timing.md`, `bottlenecks.md`, `optimizations.md`
