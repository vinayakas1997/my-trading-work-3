# Task 4: CLI + Server Wiring

**Status:** DONE

## Purpose

Expose `TradePlanOrchestrator` the same way the pre-existing `LiveScheduler` is exposed —
single-cycle CLI command, continuous worker, and an HTTP trigger route — without touching the
existing `cycle`/`worker`/`POST /cycle` surfaces for the portfolio rebalancer.

## Approach

- `cli.py`: added `trade-plan-cycle` (one cycle, prints a summary) and `trade-plan-worker`
  (continuous `while True: cycle(); sleep(interval)`, mirroring `worker_main`'s exact pattern
  including its `KeyboardInterrupt` handling) subcommands.
- `server/app.py`: added `POST /trade-plan/cycle`, mirroring the existing `POST /cycle` route
  exactly (construct orchestrator from config, run one cycle, close).
- `config.py`: added `research_api_url` (default matches `shadow_evaluator.py`'s existing
  default), `initial_analysis_api_url` (default matches `TradePlanTool`'s existing default),
  and `trade_plan_worker_interval_sec` (separate from the rebalancer's `worker_interval_sec` —
  these are different loops with different natural cadences).

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/config.py` | — | Added 2 URLs + 1 interval setting |
| `vinu_live/cli.py` | — | Added `trade-plan-cycle`/`trade-plan-worker` subcommands |
| `vinu_live/server/app.py` | — | Added `POST /trade-plan/cycle` |

## Verification

- [x] Tests pass (covered indirectly — `cli.py`/`server/app.py` import-and-route-registration
      verified manually via `create_app()` route listing; `TradePlanOrchestrator` itself has
      direct unit/integration coverage in Task 3)
- [x] Type checks pass
- [x] Manual verification done (`python -c "from vinu_live.server.app import create_app; ..."`
      confirms `/trade-plan/cycle` is registered alongside the existing routes)
- [x] No runtime LLM call introduced outside `vinu-research`
