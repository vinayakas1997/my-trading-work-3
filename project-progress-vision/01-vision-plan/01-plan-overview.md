# Phased Plan Overview

See [00-vision-summary.md](00-vision-summary.md) for the why. This file is the execution
roadmap: what ships in each phase, what it depends on, and current status.

## Status legend

`not started` · `in progress` · `shipped`

## Phases

| # | Phase | Status | Depends on | Detail |
|---|---|---|---|---|
| 1 | Monte Carlo foundation (fix, strengthen, persist) | not started | — | [phase-01-monte-carlo-foundation.md](phase-01-monte-carlo-foundation.md) |
| 2 | Wire the gate into the research refinement loop | not started | Phase 1 | [phase-02-research-gate-enforcement.md](phase-02-research-gate-enforcement.md) |
| 3 | Structured per-iteration storage | not started | Phase 2 (loose) | [phase-03-structured-iteration-storage.md](phase-03-structured-iteration-storage.md) |
| 4 | Comparative critique agent (Stage 2) | not started | Phase 3, Phase 1 | [phase-04-comparative-critique-agent.md](phase-04-comparative-critique-agent.md) |
| 5 | Trading playbook synthesis (Stage 3) | not started | Phase 1, Phase 4 | [phase-05-playbook-synthesis.md](phase-05-playbook-synthesis.md) |
| 6 | Integration testing | not started | All prior | [phase-06-integration-testing.md](phase-06-integration-testing.md) |

## Dependency chain

```
Phase 1 (Monte Carlo foundation)
   │
   ├──▶ Phase 2 (gate enforcement in research loop)
   │         │
   │         └──▶ Phase 3 (structured iteration storage) ──▶ Phase 4 (comparative critique)
   │                                                                │
   └──────────────────────────────────────────────────────────────┼──▶ Phase 5 (playbook synthesis)
                                                                     │
                                                                     ▼
                                                              Phase 6 (integration tests)
```

Phase 1 is the foundation everything else gates on: it's what makes Monte Carlo results
actually persist and become queryable instead of vanishing into an unread `run_card.json`.
Nothing downstream can enforce or display a validation result until Phase 1 ships.

Phase 3 can be built in parallel with Phase 2 (both only lightly depend on each other), but
Phase 4 hard-requires Phase 3's structured iteration table to have something to compare across
runs.

Phase 5's regime/drawdown and comparison-angle sections are hard-blocked on Phase 1 and Phase
4 respectively; its news-sensitivity and timing sections may be startable earlier if they draw
from an independent data source — confirm at implementation time.

## Files touched, by service

- **vinu-simulator** (`vinu-components/vinu-simulator/`): Phase 1 only.
  - `vinu_simulator/engine/validation.py`
  - `vinu_simulator/service.py`
  - `vinu_simulator/storage/meta.py`
  - `vinu_simulator/server/schemas.py`
  - `vinu_simulator/server/routes_read.py`
  - `tests/test_validation.py`, `tests/test_service.py`, `tests/test_meta.py` (new)

- **vinu-research** (`vinu-components/vinu-research/`): Phases 2, 3, 4, 6.
  - `vinu_research/tools.py`
  - `vinu_research/loop.py`
  - `vinu_research/llm.py`
  - `vinu_research/storage/sqlite_backend.py`
  - `vinu_research/comparative_critic.py` (new)
  - `vinu_research/service.py`

- **vinu-agent** (`vinu-components/vinu-agent/`): Phases 1 (bugfix), 5, 6.
  - `vinu_agent/tools/trade_plan_tool.py`
  - `vinu_agent/tools/backtest_tool.py` (Phase 6, optional param exposure)

## Approval status

Only **Phase 1** is approved to begin implementation. Phases 2–6 are documented here so the
team has the full picture, but each requires its own review/approval before code is written,
since later phases may need re-scoping once Phase 1's actual shape is known.

## Advanced vision (Phases 7–10)

Phases 1–6 above get a strategy validated once, refined, compared, and documented — necessary
but not sufficient for trusting it with real capital. [02-advanced-vision.md](02-advanced-vision.md)
covers four further phases addressing that gap: family-wise overfitting control and
parameter-surface robustness ([phase-07](phase-07-overfitting-and-robustness.md)), a
portfolio-level correlation gate ([phase-08](phase-08-portfolio-correlation-gate.md)),
shadow/paper validation plus continuous re-validation ("Stage 4",
[phase-09](phase-09-shadow-live-validation.md)), and LLM judgment calibration plus cost realism
([phase-10](phase-10-judgment-quality-and-cost-realism.md)). None of these are approved to
start; they're documented for planning purposes only.
