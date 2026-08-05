# BUG-06 🔵 VINU_DEBUG Timing Instrumentation

**Component:** `vinu-infra`, `vinu-research`, `vinu-simulator`, `vinu-initial-analysis`
**Files Changed:** Multiple files (see below)
**Date Found:** 2026-07-23
**Date Fixed:** 2026-07-23

## Problem

No timing instrumentation existed in the research pipeline. When debugging why
`POST /research/run` returned `total_iterations=0`, there was no way to see:
- How long each step took
- Which component was the bottleneck
- Where failures occurred

## Root Cause

The codebase had no shared debugging utility. Each component used its own logging
with no consistent format or timing mechanism.

## Suggested Fix

Create a shared `debug.py` utility in `vinu-infra` with:
- `setup_logging(service_name)` — centralized logging config
- `debug_timer(label)` — async context manager for timing
- `sync_timer(label)` — sync context manager for timing
- `debug_log(msg)` — conditional debug log
- `is_debug()` — check if VINU_DEBUG is enabled

## Actual Fix

Created `/home/somic_cps/Vina/my-trading-work-3/vinu-components/vinu-infra/vinu_infra/debug.py`
(initially in wrong location, see BUG-07).

Then moved to correct location: `/home/somic_cps/Vina/my-trading-work-3/vinu-components/vinu-infra/debug.py`

### Files Modified

1. **`vinu-infra/vinu_infra/debug.py`** (created) — `setup_logging()`, `debug_timer()`, `sync_timer()`
2. **`vinu-components/.env`** — Added `VINU_DEBUG=false`
3. **`vinu-components/docker-compose.yml`** — Added `VINU_DEBUG: ${VINU_DEBUG:-false}` to all 17 services
4. **10 CLI entry points** — Added `setup_logging("service-name")`
5. **`vinu-infra/client.py:170-174`** — Wrapped `_request` with `debug_timer`
6. **`vinu-infra/llm/client_async.py:114`** — Wrapped `chat_json` POST with `debug_timer`
7. **`vinu-research/loop.py`** — Added timers around gen, backtest, walk-forward, stress-test
8. **`vinu-simulator/service.py`** — Added timer around `simulate_custom`
9. **`vinu-simulator/engine/custom_sim.py:55-57`** — Added sync_timer around `generate_weights`
10. **`vinu-initial-analysis/runner.py:94-96`** — Added sync timer around angle computation

## Verification

1. Set `VINU_DEBUG=true`
2. Run research pipeline
3. Confirm `[TIMER]` logs appear with START/END timestamps
4. Confirm bottlenecks are visible (e.g., LLM calls taking 90s+)

## Lessons Learned

- Always instrument critical paths early — it saves hours of debugging
- Use a shared utility library (`vinu-infra`) for cross-component tools
- File placement matters: `pip install -e` expects modules at package root level
- `debug_timer` with indent tracking helps visualize concurrent operations
