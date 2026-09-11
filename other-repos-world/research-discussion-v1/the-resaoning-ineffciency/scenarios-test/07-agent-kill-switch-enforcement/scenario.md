# Scenario 07 — vinu-agent-side kill-switch enforcement

## Plan

Written before anything is run. Re-verified against the real code first
(not assumed): the actual authoritative enforcement point for the
reduce_only-exemption-during-a-halt claim (flagged as scenario 02's own
gap: "an orchestrator-level scenario can't reach OrderGuard's real check")
is `OrderGuard.check()` in `vinu-agent/vinu_agent/broker/order_guard.py`:

```python
if is_trading_halted(scope=symbol):
    if reduce_only and _halt_policy_allows_reduce_only():
        logger.warning(...)  # allowed through
    else:
        return GuardResult(False, "Trading is halted by kill switch", ...)
```

`_halt_policy_allows_reduce_only()` reads `VINU_LIVE_HALT_POLICY`
(default `"entries_only"`) — the same env var `vinu-live`'s own local
breaker reads, deliberately, so one policy switch governs both halt
layers rather than two that could silently disagree.

Checked the existing test coverage (`test_order_guard.py`,
`TestKillSwitchScope`) before writing this: every halt-related test there
mocks `is_trading_halted` directly via `patch(...)`, and only ONE test
(`test_global_halt_blocks_any_symbol`) ever sets it to `True` — and that
test only exercises a plain `buy` order (not `reduce_only`). **No existing
test combines `is_trading_halted() == True` with `reduce_only=True`** —
the exact exemption this scenario exists to prove. This confirms scenario
02's flagged gap is real, not already covered elsewhere.

Going one step further than mocking `is_trading_halted` (the existing
file's convention): this scenario uses the REAL `halt_trading()` /
`resume_trading()` functions from `kill_switch.py` — the actual
filesystem-backed global kill switch (`/tmp/vinu-trading-halt`) — against
a real `OrderGuard` instance, the most authentic version of this claim
reachable without a live broker. `test_kill_switch.py` already establishes
the safe pattern for this (an autouse fixture that resumes/clears the
switch before and after every test, so a test never leaves the real
switch engaged for anything else running on the machine) — reused here
rather than reinvented.

Three sub-cases:
1. **Halted + reduce_only, default policy (`entries_only`)**: must be
   allowed through.
2. **Halted + NOT reduce_only, default policy**: must be rejected
   (`KILL_SWITCH_HALT`).
3. **Halted + reduce_only, policy set to something other than
   `entries_only`** (e.g. `"always"`): the exemption itself must also be
   policy-gated, not unconditional — must be rejected too, proving the
   exemption isn't a blanket "reduce_only always bypasses the kill
   switch," it's specifically the configured policy's decision.

## Expected Result

1. Case 1: `GuardResult.allowed is True`.
2. Case 2: `GuardResult.allowed is False`, `code == ReasonCode.KILL_SWITCH_HALT`.
3. Case 3: `GuardResult.allowed is False`, `code == ReasonCode.KILL_SWITCH_HALT`
   — same rejection as case 2, despite `reduce_only=True`, because the
   policy no longer grants the exemption.
4. No real filesystem kill-switch state is left engaged after the test
   run (verified via the same clean-up fixture `test_kill_switch.py` uses).

## Execution Result

Built as `vinu-agent/tests/test_kill_switch_reduce_only_exemption.py::TestRealKillSwitchReduceOnlyExemption`, 4 tests (the 3 planned cases plus a sanity control confirming the two blocked cases are actually caused by the halt, not an unrelated mandate check):

```
test_reduce_only_order_allowed_through_a_real_halt_default_policy PASSED
test_non_reduce_only_order_blocked_by_a_real_halt_default_policy PASSED
test_reduce_only_exemption_itself_is_policy_gated_not_unconditional PASSED
test_no_halt_allows_both_kinds_of_order PASSED
```

`ls /tmp/vinu-trading-halt` after the run: no such file -- the real global
kill switch was correctly left clear.

Full `vinu-agent` suite: 1009 passed, 4 skipped, 9 pre-existing unrelated failures
(`test_config.py`, `test_routes_broker.py`, `test_service.py` -- confirmed
identical via `git stash` before/after, same discipline as every other
scenario in this audit; this is the first scenario run against
`vinu-agent` rather than `vinu-live`, so this is that baseline established
for the first time here).

One real fix needed along the way, not in the kill-switch logic itself: a
`reduce_only` sell with no broker position on record for that symbol
tripped an unrelated mandate check ("Short selling is not permitted") --
resolved by setting `allow_short=True` on the test mandate, since this
scenario is specifically about the kill-switch check, not short-selling
policy.

## Reasoning

Confirmed exactly what scenario 02 could not reach: `OrderGuard.check()`'s
reduce_only exemption during a real, filesystem-level halt works as
designed, and is genuinely policy-gated (case 3 proves `reduce_only=True`
is not itself a blanket bypass -- it only clears the kill switch when
`VINU_LIVE_HALT_POLICY=entries_only`, the same switch `vinu-live`'s own
local breaker reads, by design, so an operator has one policy to reason
about instead of two that could silently disagree).

This closes the loop scenario 02 explicitly could not: that scenario
proved the *orchestrator's* local halted-flag never blocks an exit; this
one proves the *actual authoritative* enforcement point -- the real
`OrderGuard.check()`, against the real filesystem kill switch, not a
mocked stand-in for either -- makes the identical decision. Together they
cover both ends of the one call that matters in production:
`vinu-live` submits a reduce_only order during a halt, and
`/agent/broker/order` -> `TradeTool` -> `OrderGuard.check()` is what
actually has to let it through.

Also worth noting for the trust question this whole audit is about: this
is the deepest "real, not mocked" component reachable in the pre-live
mechanical suite -- an actual OS-level file the kill switch reads,
touched by the actual `halt_trading()` function a real operator or a real
drawdown monitor would call. The only thing NOT real here is the broker
itself (`MagicMock()`), which is appropriate: this scenario is about
whether the safety gate opens correctly, not about broker connectivity
(already covered by scenarios 04 and 06).

## Action Taken

**No fix needed to the kill-switch/reduce_only logic** -- the real
behavior matched the known-correct answer on the first attempt once the
unrelated short-selling mandate check was set aside for this test's
scope. This closes the last flagged gap from `scenarios-test`.

No new gaps flagged from this one.
