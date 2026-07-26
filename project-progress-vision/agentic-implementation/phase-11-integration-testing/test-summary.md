# Phase 11 — Test Summary

## Tests Run

### vinu-agent — Context + Memory

| Test | Result |
|------|--------|
| `test_memory_appears_in_context` | PASS |
| `test_no_memory_for_unmentioned_symbol` | PASS |
| `test_dedup_prevents_duplicate_source_id` | PASS |
| `test_token_budget_truncates_low_priority` | PASS |

### vinu-research — Catalog Exhaustion

| Test | Result |
|------|--------|
| `test_validation_failure_increments_counter` | PASS |
| `test_validation_pass_resets_counter` | PASS |
| `test_auto_exhaust_after_five_failures` | PASS |
| `test_high_trial_low_sharpe_exhaustion` | PASS |
| `test_inexhausted_symbol_returns_false` | PASS |
| `test_exhaust_and_clear` | PASS |
| `test_exhaust_symbol_manually` | PASS |
| `test_loop_returns_early_when_exhausted` | PASS |
| `test_loop_runs_normally_when_not_exhausted` | SKIP (needs simulator) |

### vinu-research — Promotion + Correlation Gate

| Test | Result |
|------|--------|
| `test_approve_creates_active_when_gate_disabled` | PASS |
| `test_approve_creates_active_when_gate_passes` | PASS |
| `test_approve_creates_benching_when_gate_blocks` | PASS |
| `test_approve_no_active_strategies_still_activates` | PASS |
| `test_approve_preserves_artifact_contents` | PASS |

## Summary

- **17 total** (16 active + 1 skipped)
- **16 PASS, 1 SKIP** (test_loop_runs_normally_when_not_exhausted requires a running simulator at http://127.0.0.1:8085)
- **0 FAIL, 0 ERROR**

## Coverage Notes

- Agent-side integration tests run without any external infrastructure.
- Research exhaustion tests use in-memory SQLite for catalog operations; the loop early-exit test verifies the exhaustion check path (no simulator needed).
- Promotion tests mock the correlation gate to test all three branches (gate disabled, gate passes, gate blocks) and verify artifact contents/statuses.
- The one skipped test validates that a non-exhausted symbol proceeds past the early-exit check into the full research loop — requires a live simulator.

## Verdict

All verifiable tests pass. No regressions detected.
