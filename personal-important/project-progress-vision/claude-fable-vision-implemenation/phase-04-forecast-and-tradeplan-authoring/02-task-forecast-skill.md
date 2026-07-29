# Task 2: Forecast Skill

**Status:** DONE

## Purpose

Implement `generate_forecast()` that produces direction+magnitude forecasts using Phase 2 personality features + Phase 1 risk state, and `compute_calibration()`/`CalibrationGate` scaffolding (see Task 3) to gate approval.

## Approach

- `generate_forecast()`: calls the research LLM client with Phase 1 risk data + Phase 2
  personality stats, falls back to a neutral forecast on any non-JSON/failed response.
- `compute_brier_score` / `compute_directional_error` / `compute_calibration`: pure functions
  scoring forecast accuracy vs. a coin-flip null (accuracy), vol-implied null (magnitude MAPE),
  and Brier score, each gated by `ForecastSkillConfig`'s improvement thresholds.

## Bug found and fixed during implementation

The version of this file present at session start imported `from vinu_research.loop import
_LLM` — that symbol does not exist anywhere in `loop.py`, so `generate_forecast()` would raise
`ImportError` the first time it was called. It also parsed an OpenAI `choices[0].message.content`
response shape that doesn't match this codebase's actual LLM client. Rewrote it to accept a
`ResearchLlmClient`-shaped object (`async chat_json(system, user) -> dict | None`), matching the
pattern already used in `service.py:449` and `loop.py:142`; constructs one from `ResearchConfig`
when no client is passed.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_research/forecast_skill.py` | 1-70, 131-171 | Removed unused `json` import; fixed `generate_forecast()`'s broken LLM call (see above) |

## Verification

- [x] Tests pass (`tests/test_forecast_skill.py`, 14 tests)
- [x] No runtime LLM call introduced outside `vinu-research`
