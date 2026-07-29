# Task 5: Artifact Freeze for Trade Plans

**Status:** DONE

## Purpose

Wire the freeze→approve flow for trade plans into the existing Artifact storage. Once
approved (`ACTIVE`), a TradePlan cannot be mutated — revisions require authoring and freezing
a new artifact.

## Approach

- `trade_plan_data` TEXT column on `artifacts` (already present in `strategy_store.py` schema
  + migration from the prior session — verified correct, no change needed).
- `trade_plan_authoring.freeze_trade_plan(store, plan)`: creates
  `Artifact.create(type_="trade_plan", ...)`, sets `trade_plan_data = plan.to_json()`, persists
  via the existing `upsert_artifact` — status stays `CREATED`.
- `trade_plan_authoring.approve_trade_plan(store, artifact_id, tracker)`: loads the artifact,
  rejects (`TradePlanApprovalError`) if it's already `ACTIVE` (immutability — enforced at this
  function's entry, not a DB trigger), runs `CalibrationGate(tracker).check()`, only flips to
  `ACTIVE` on `passed=True`. Fails closed: a freshly frozen plan has zero calibration entries
  (those accumulate from Phase 6/7's realized-outcome feedback, not built yet) and so cannot be
  approved yet — this is intentional, not a bug; `plan.md` row 7 explicitly assigns live
  calibration feedback to Phase 7.
- HTTP surface: `POST /research/trade-plan/{symbol}` (author+freeze), `GET
  /research/trade-plan/{artifact_id}`, `POST /research/trade-plan/{artifact_id}/approve` —
  new `server/routes_trade_plan.py`, registered in `server/app.py`.

## Files Changed

| File | Lines | What Changed |
|-------|-------|-------------|
| `vinu_research/models.py` | — | `trade_plan_data` on `Artifact` — already present, verified |
| `vinu_research/storage/strategy_store.py` | — | Schema/CRUD for `trade_plan_data` — already present, verified |
| `vinu_research/trade_plan_authoring.py` | new file | `fetch_risk_state`, `fetch_personality_features`, `author_trade_plan`, `freeze_trade_plan`, `approve_trade_plan`, `TradePlanApprovalError` |
| `vinu_research/server/routes_trade_plan.py` | new file | Freeze/get/approve HTTP endpoints |
| `vinu_research/server/app.py` | 7, 13, 17 | Registered `routes_trade_plan` router |

## Verification

- [x] Tests pass (`tests/test_trade_plan_authoring.py` 12 tests, `tests/test_routes_trade_plan.py` 6 tests)
- [x] Immutability: `test_approve_rejects_mutation_once_active` confirms a second approve call on an already-`ACTIVE` plan raises
