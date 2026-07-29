# Phase 7 — Test Summary

## Tests Run

| Test File | Test Count | Result |
|-----------|-----------|--------|
| `vinu-live/tests/test_book.py` (extended) | 22 (5 new) | PASS |
| `vinu-live/tests/test_feedback_loop.py` | 12 | PASS |
| `vinu-research/tests/test_calibration_persistence.py` | 12 | PASS |
| `vinu-research/tests/test_trade_plan_authoring.py` (updated) | 12 | PASS |
| `vinu-research/tests/test_routes_trade_plan.py` (extended) | 9 (3 new) | PASS |
| `vinu-initial-analysis/tests/test_pnl_attribution.py` | 11 | PASS |

New Phase 7 tests: 43 (17 vinu-live + 15 vinu-research + 11 vinu-initial-analysis). Full suites:
`vinu-live` 115/115, `vinu-research` 483 passed / 17 pre-existing-unrelated failures (one of
which — `test_sqlite_backend.py::TestThreadSafety::test_concurrent_writes` — is flaky, not a
regression: it passed in isolation and on a full-suite rerun; confirmed via `git status` that
`test_sqlite_backend.py` was never touched this session), `vinu-initial-analysis` 97/97,
`vinu-agent` 177/177 (re-run as a cross-check since it consumes `vinu-research`'s trade-plan
endpoints, though nothing in it changed this phase).

## Bugs found during implementation (both caught by tests, not code review)

1. **`approve_trade_plan` could never actually succeed.** The HTTP route built a fresh, empty
   `CalibrationTracker` on every call — no amount of recorded outcomes could ever pass the
   gate. Found while writing `test_calibration_persistence.py`'s reconstruction test; fixed by
   making `approve_trade_plan` always rebuild from persisted storage
   (`load_calibration_tracker`), never from a caller-supplied tracker.
2. **`pnl_attribution`'s `closed_positions` column broke JSON serialization.** Parquet
   round-trips a list-of-dicts column as a numpy object array; FastAPI's encoder can't
   serialize it, so `GET /angle/pnl_attribution/{symbol}` 422'd. Only caught because
   `test_pnl_attribution.py` included a route-level test through the real HTTP app in addition
   to unit tests against the pure aggregation/ingest functions — the unit tests alone never
   exercised JSON serialization and would have passed regardless. Fixed by storing the field as
   a JSON string.

## Coverage Notes

- `_realized_return_pct`'s long/short sign convention is directly tested — the case that would
  most easily be gotten backwards (a profitable short reporting a *negative* underlying return,
  not a positive P&L-sign return) has its own test.
- `FeedbackLoopWorker.cycle()` is tested for: no unprocessed positions (skip), full processing
  with all three write-backs firing, idempotency (a second cycle re-sends nothing), resilience
  to outbound HTTP failures (position still marked processed — no infinite-retry pileup), the
  targeted-refresh call's exact params (`angle_names` + a `to_ts` present on every call, since
  omitting it would hit the runner's dedup-skip), and structural absence of any dependency on
  `trade_plan/orchestrator.py`.
- `ingest_closed_positions` is tested for first-batch population, multi-batch accumulation, and
  redelivery dedup by `position_id` — the three behaviors the design depends on for correctness
  under retries.
- `approve_trade_plan`'s fail-then-succeed path is tested end-to-end through the real HTTP
  routes (`test_succeeds_once_enough_realized_outcomes_recorded`), not just at the Python-API
  level — this is the test that would have caught bug #1 even without the dedicated persistence
  test file.
- Not tested (deliberately out of scope): real broker/paper-trading execution producing real
  closed positions (Phase 6 already covers order submission with mocked HTTP; nothing new to
  add here), and any cold-start heuristic for a plan's very first approval before any realized
  history exists — the source doc frames this as intentionally out of scope for this vision.

## Verdict

All new and pre-existing tests pass across all four packages touched or cross-checked
(`vinu-live`, `vinu-research`, `vinu-initial-analysis`, `vinu-agent`). The one pre-existing
`vinu-research` failure count (17) is unchanged and confirmed unrelated; the one additional
failure seen on a single run was confirmed flaky, not a regression. Two real bugs were found
and fixed during implementation, both via tests that exercised behavior a narrower test suite
would have missed (persisted-state reconstruction, HTTP-boundary serialization).
