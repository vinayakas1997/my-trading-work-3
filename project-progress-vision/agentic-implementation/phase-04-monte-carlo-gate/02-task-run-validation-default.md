# Task 2: Default `run_validation=True` in run_backtest

**Status:** DONE

## Purpose

The research loop calls `run_backtest()` which POSTs to `/simulate/custom`. The request body must include `run_validation: true` so the simulator computes MC validation and returns it in the response.

## Approach

Add `run_validation: bool = True` parameter to `ResearchTools.run_backtest()` and include it in the POST body dict.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/tools.py` | 46-67 | Added `run_validation=True` param and `body["run_validation"] = run_validation` |

## Verification

- [x] 401/401 research tests pass
