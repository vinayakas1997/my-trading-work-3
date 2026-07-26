# Task 3: `pnl_attribution` Angle + Targeted Phase 2 Refresh

**Status:** DONE

## Purpose

Build the `pnl_attribution` angle from scratch (it did not exist — see `00-implementation.md`
discovery #1) and expose the `AngleRunner`'s existing-but-unexposed `angle_names` filter over
HTTP so Phase 7 can refresh just `shock_personality`/`shock_clustering`, not the full angle
suite, when a symbol has a new realized shock/trade.

## Approach

- `angles/pnl_attribution/compute.py`: `aggregate_pnl_attribution(symbol, closed_positions)` —
  pure aggregation (win rate, avg win/loss, trade count, total realized PnL), each stat
  carrying sample size + 95% CI matching `shock_personality`'s confidence-scored-fact
  convention. `compute()` keeps the standard runner signature as a documented no-op
  (`status: "push_fed_not_runner_driven"`) so a generic `/run/{ticker}` sweep doesn't error.
- `pnl_attribution_ingest.py`: `ingest_closed_positions(storage, symbol, closed_positions)` —
  reads prior history via `AngleStorage.read_latest`, dedupes the merged set by `position_id`
  (a retried feedback-loop cycle re-delivering the same closed position never double-counts
  it), re-aggregates, writes via `AngleStorage.write()` directly — bypassing the bars-driven
  runner entirely, since `AngleStorage.write()` is angle-agnostic.
- `POST /pnl-attribution/{ticker}/record`: the HTTP front door onto `ingest_closed_positions`.
- `POST /run/{ticker}` gained an optional `angle_names` query param (comma-separated), threaded
  through `InitialAnalysisService.run_analysis` → `CorrelationAPI.compute_and_store` →
  `AngleRunner.run` (which already accepted `angle_names` — it just wasn't reachable over HTTP).

## Bug found and fixed during implementation

`aggregate_pnl_attribution` originally stored the accumulated `closed_positions` list directly
as a DataFrame column. Parquet round-trips a list-of-dicts column as a numpy object array on
read, and FastAPI's JSON encoder can't serialize that — `GET /angle/pnl_attribution/{symbol}`
returned HTTP 422. Only caught because the test suite included a route-level test through the
real HTTP app, not just unit tests against `aggregate_pnl_attribution`/`ingest_closed_positions`
directly (which never exercise JSON serialization). Fixed by storing `closed_positions_json`
(a JSON string) instead — the same pattern `vinu-research`'s `Artifact.universe` already uses
for a list-valued column in a flat storage row.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_initial_analysis/angles/pnl_attribution/compute.py` | — | Created |
| `vinu_initial_analysis/angles/pnl_attribution/spec.yaml` | — | Created |
| `vinu_initial_analysis/pnl_attribution_ingest.py` | — | Created |
| `vinu_initial_analysis/server/routes_read.py` | — | `POST /pnl-attribution/{ticker}/record`; `angle_names` on `POST /run/{ticker}` |
| `vinu_initial_analysis/service.py`, `api.py` | — | `angle_names` threaded through `run_analysis`/`compute_and_store` |

## Verification

- [x] Tests pass (`tests/test_pnl_attribution.py`, 11 tests — including the route-level test that caught the serialization bug above)
- [x] No runtime LLM call introduced outside `vinu-research`
