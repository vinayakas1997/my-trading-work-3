# Task 1: TradePlan Model

**Status:** DONE

## Purpose

Define the TradePlan dataclass, ContingencyRule, InvalidationCondition, and RiskBand models that constitute the machine-evaluable trade plan contract.

## Approach

- TradePlan: sizing, risk_bands, contingency_rules, invalidation_conditions, forecast
- ContingencyRule / InvalidationCondition: `metric` + `operator` + `threshold` fields (a
  triple Phase 6 can evaluate directly against live data), not a free-text `condition` string.
  `condition` is kept only as an auto-derived human-readable label
  (`f"{metric} {operator} {threshold}"`), never the source of truth. `operator` is validated
  against a fixed set (`>=`, `<=`, `>`, `<`, `==`, `!=`) in `__post_init__`.
- `TradePlan.from_json` reconstructs the nested `RiskBand`/`ContingencyRule`/
  `InvalidationCondition`/`Forecast` dataclasses (not plain dicts) so a frozen plan round-trips
  through storage as typed objects.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_research/models.py` | ~145-270 | Added `RiskBand`, `ContingencyRule`, `InvalidationCondition`, `Forecast`, `TradePlan`, `CalibrationEntry`, `CalibrationResult`; fixed `TradePlan.from_json` to reconstruct nested dataclasses instead of leaving them as raw dicts |

## Verification

- [x] Tests pass (`tests/test_trade_plan_authoring.py::TestFreezeAndApprove::test_freeze_persists_as_created` round-trips a `TradePlan` through `to_json`/`from_json`)
- [x] Manual: `ContingencyRule(metric=..., operator="bad", threshold=0.0, action=...)` raises `ValueError`
