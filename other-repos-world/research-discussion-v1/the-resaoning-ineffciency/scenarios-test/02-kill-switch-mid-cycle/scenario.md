# Scenario 02 — Kill switch engaged mid-cycle

## Plan

Written before anything is run. Re-verified against the real code before
writing this (not assumed): `_trading_halted` (the local mirror of the
agent's global kill switch, refreshed once per `cycle()` via
`_is_trading_halted()`) is checked in exactly one place —
`_maybe_enter()`. It is never referenced anywhere in
`_evaluate_open_position()` / `_apply_invalidation()` /
`_apply_contingency()` / the rebalance/bracket paths. The actual
reduce-only-exemption enforcement happens downstream, at OrderGuard
(`vinu-agent`), when the real order hits `/agent/broker/order` — outside
what this mocked orchestrator-level harness can observe (same boundary
scenario 01 already ran into with the broker-side resting stop).

So what THIS scenario can honestly test, at the orchestrator level: one
real `cycle()` call, with the kill switch reporting halted, evaluating
**two symbols in the same cycle** —
- **MSFT**: no open position, an eligible entry signal. Expected to be
  blocked.
- **AAPL**: an open position whose price now triggers the plan's
  invalidation condition. Expected to still exit.

Existing tests already prove each behavior in isolation
(`test_halted_flag_blocks_new_entries`,
`test_cycle_blocks_entry_when_agent_reports_halt`) — neither combines a
blocked entry and a live exit in the same cycle. That combination, not
either behavior alone, is the actual thing worth proving: that a halted
cycle doesn't accidentally also freeze exits it was never supposed to
touch.

## Expected Result

1. `cycle()`'s `actions` list contains one `entry_blocked_by_emergency_halt`
   for MSFT and one `invalidation_exit` for AAPL — both in the same cycle
   result, not two separate runs.
2. No order is submitted for MSFT (entry never reaches `_submit_order`).
3. A real `reduce_only` sell order is submitted for AAPL, and the book
   position closes.
4. `result["trading_halted"]` is `True`.

## Execution Result

Built as `vinu-live/tests/test_pre_live_scenarios.py::TestScenarioKillSwitchMidCycle::test_entry_blocked_and_exit_still_fires_in_the_same_cycle`:

```
tests/test_pre_live_scenarios.py::TestScenarioKillSwitchMidCycle::test_entry_blocked_and_exit_still_fires_in_the_same_cycle PASSED
```

Full `vinu-live` suite after: 308 passed (2 pre-existing, unrelated `test_auth.py` failures — same baseline throughout this audit).

All four points from Expected Result held exactly, first try:
- `result["actions"]` contained `entry_blocked_by_emergency_halt` for MSFT and `invalidation_exit` for AAPL, both from the same `cycle()` call.
- Exactly one `/broker/order` call was made, for AAPL, `reduce_only=True` — no order was ever attempted for MSFT.
- The AAPL book position closed.
- `result["trading_halted"]` was `True`.

## Reasoning

Same shape of result as scenario 01: this didn't find a bug, it confirmed a real design decision actually holds when exercised, not just when read. `_trading_halted` genuinely is checked in exactly one place (`_maybe_enter`) and genuinely has zero effect on `_evaluate_open_position`'s exit path — the separation the code comments claim ("OrderGuard rejects on it; reduce_only exits stay allowed") is real at the orchestrator level too, not just delegated-and-hoped-for at the agent level.

The honest boundary, same as scenario 01: this only proves the orchestrator's own halted-flag handling. It cannot observe whether `OrderGuard`'s kill-switch + reduce-only exemption (the actual authoritative enforcement, in `vinu-agent`, reached over the mocked `/agent/broker/order` HTTP call) behaves the same way — that would need a test hitting the real `TradeTool`/`OrderGuard`/`kill_switch.py` code in `vinu-agent`, not this mocked orchestrator harness. `trade_tool.py`'s own tests (`test_trade_tool.py`, `test_trade_tool_audit_trail.py`) don't currently include a live-kill-switch-engaged case either — candidate for a future scenario in `vinu-agent`, not this suite.

## Action Taken

**No fix needed** — the real behavior matched the known-correct answer on the first run.

**Flagged for later, not this scenario's scope**: a `vinu-agent`-side test confirming `OrderGuard`'s real kill-switch check actually allows a `reduce_only=True` order through while a halt is engaged (the actual authoritative enforcement this orchestrator-level scenario can't reach). Candidate for `llm-scenarios-test` or a new `vinu-agent`-side scenarios folder, not `vinu-live`'s.

**2026-09-11 addendum, from scenario 06**: this scenario's `/broker/positions` mock was a `[]` convenience default that, after scenario 06's fix, would have resolved to `broker_flat` (book-only close, no order) instead of a real order — not what this scenario was testing (whether the halt blocks the entry while letting the exit through, regardless of the broker-flat mechanism). The mock was updated to show a broker that actually holds the AAPL position, so the test keeps proving exactly what it always did. This scenario's documented conclusion is unchanged.
