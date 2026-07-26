# Phase 4: Forecast Skill + Full Trade-Plan Authoring (hinge phase)

**Status:** COMPLETED
**Started:** 2026-07-26
**Completed:** 2026-07-27
**Source doc:** ../claude-fable-vision/phase-04-forecast-and-tradeplan-authoring.md
**Depends on:** Phase 1, Phase 2
**Blocks:** Phase 6, Phase 7

## What It Delivers

Two parts shipping together:

1. **Forecast skill** — direction + magnitude built from Phase 2's personality features and Phase 1's risk state, gated by a calibration test (directional accuracy vs coin-flip, magnitude error vs vol-implied null, scored with Brier/CRPS). Calibration tracked continuously — failing forecasts are automatically blocked from approval.

2. **Full trade-plan authoring** — extends `TradePlanTool` from checklist-rendering to producing a complete, binding, machine-evaluable contract: position size, risk bands (Phase 1 formulas + Phase 2 context), in-trade contingency rules (boolean conditions over defined inputs), invalidation conditions. Frozen as a versioned `Artifact` with `type="trade_plan"`.

## Open Questions Resolved

- **Storage location**: Frozen trade plans stored as `Artifact` with `type="trade_plan"` in `vinu-research`'s existing `SqliteStrategyStore`. A new `trade_plan_data` TEXT column holds JSON-serialized `TradePlan` object. This reuses the existing approve→artifact bridge and avoids a new storage layer.

## Files Touched

Note: the TradePlan model ended up living in `models.py` directly (not a separate
`trade_plan.py`) — matching how every other artifact-adjacent model already lives there
(`BacktestMetrics`, `DecaySnapshot`, `StoryBlock`, ...). No `vinu-strategy` involvement was
needed; the Open Design Question below resolves storage entirely inside `vinu-research`.

| File | Service | Change Type |
|------|---------|-------------|
| `vinu_research/models.py` | vinu-research | modify — `RiskBand`, `ContingencyRule`, `InvalidationCondition`, `Forecast`, `TradePlan`, `CalibrationEntry`, `CalibrationResult` |
| `vinu_research/forecast_skill.py` | vinu-research | modify — fixed broken LLM call (see Task 2) |
| `vinu_research/calibration.py` | vinu-research | verified, no change needed |
| `vinu_research/trade_plan_authoring.py` | vinu-research | create — orchestration: risk state + personality fetch, author/freeze/approve |
| `vinu_research/server/routes_trade_plan.py` | vinu-research | create — freeze/get/approve HTTP endpoints |
| `vinu_research/server/app.py` | vinu-research | modify — registered `routes_trade_plan` |
| `vinu_research/storage/strategy_store.py` | vinu-research | verified, no change needed (`trade_plan_data` column already present) |
| `vinu_agent/tools/trade_plan_tool.py` | vinu-agent | modify — consumes the frozen plan via HTTP, no LLM call added |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-tradeplan-model.md` | TradePlan dataclass, ContingencyRule, InvalidationCondition | DONE |
| 2 | `02-task-forecast-skill.md` | generate_forecast + calibration scoring functions | DONE |
| 3 | `03-task-calibration-tracking.md` | CalibrationTracker + CalibrationGate | DONE |
| 4 | `04-task-tradeplan-tool-extension.md` | TradePlanTool consumes frozen plan via HTTP | DONE |
| 5 | `05-task-artifact-freeze.md` | freeze/approve orchestration + HTTP endpoints | DONE |

## Dependencies Met

- [x] Phase 1 completed (risk-math: VaR, greeks, expected move, sizing, covariance)
- [x] Phase 2 completed (personality angles: gap_fill_rate, vol_persistence, shock_cluster_membership)

## Completeness Test (plan.md's "Warning for whoever implements Phase 4")

Every `ContingencyRule`/`InvalidationCondition` on an authored `TradePlan` is a
`metric`/`operator`/`threshold` triple (e.g. `drawdown_pct >= 0.05 -> reduce_position`), not a
free-text instruction — see `models.py`'s `ContingencyRule`/`InvalidationCondition` and the
`operator` allow-list enforced in `__post_init__`. `test_trade_plan_authoring.py`'s
`test_produces_complete_plan` asserts this mechanically for every rule on an authored plan.
`author_trade_plan` always produces at least: a drawdown-based reduce rule, a realized-vol-vs-
GARCH-forecast tighten-stop rule, a gap-against-position exit, an unrealized-PnL exit, and
(when Phase 2 reports shock-cluster membership) a cluster-correlation reduce rule — Phase 6
never needs to ask an LLM what to do for any of these; they're pre-evaluated conditions over
live inputs.

**Known scope boundary, not a completeness gap:** `approve_trade_plan` correctly fails closed
on a freshly frozen plan (zero calibration entries) — live/realized-outcome calibration
feedback is explicitly Phase 7's job (`plan.md` row 7), not Phase 4's. The gate mechanism
itself is complete and tested (`test_calibration.py`, `test_trade_plan_authoring.py`); what's
missing is the feedback data source, which doesn't exist until Phase 6/7 run trades.

## Non-Negotiable Rule Check (AGENTS.md Rule 10)

The only LLM call in this phase (`forecast_skill.generate_forecast`, via `ResearchLlmClient`)
executes inside `vinu-research`, called from `trade_plan_authoring.author_trade_plan`, invoked
from `server/routes_trade_plan.py`'s `POST /research/trade-plan/{symbol}` handler — all inside
`vinu-research`. `vinu_agent/tools/trade_plan_tool.py` only issues an HTTP POST to that
endpoint and renders the JSON response; it contains no LLM call, matching `plan.md`'s Files
Touched table role for `vinu-agent` ("consumers of Phase 4's frozen plans... not the authoring
surface itself").
