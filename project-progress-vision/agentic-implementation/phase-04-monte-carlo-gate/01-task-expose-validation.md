# Task 1: Expose Validation in Simulator API Response

**Status:** DONE

## Purpose

The validation data computed in `service.py` (Monte Carlo permutation, bootstrap, walk-forward, etc.) was previously only written to the run card on disk — it was not returned in the API response. The research loop needs it at runtime to short-circuit strategies that fail the MC gate.

## Approach

1. Add `validation: dict[str, Any] | None = None` field to `SimulationResult` dataclass
2. Add `validation: dict[str, Any] | None = None` to `SimulateResponse` and `CustomSimulateResponse` Pydantic schemas
3. Set `result.validation = validation` in both `_simulate_impl` and `_simulate_custom_impl` after computing validation
4. Pass `validation=result.validation` in both route handlers

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-simulator/vinu_simulator/models/simulation.py` | 90 | Added `validation` field to `SimulationResult` |
| `vinu-simulator/vinu_simulator/server/schemas.py` | 34, 95 | Added `validation` to `SimulateResponse` and `CustomSimulateResponse` |
| `vinu-simulator/vinu_simulator/server/routes_read.py` | 63, 78 | Added `validation=result.validation` to response construction |
| `vinu-simulator/vinu_simulator/service.py` | 175, 348 | Added `result.validation = validation` after computing it |

## Verification

- [x] 121/121 simulator tests pass
