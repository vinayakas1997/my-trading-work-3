# llm-scenarios-test

Acceptance scenarios for the real LLM agent loop -- the untested layer:
everything checked in `vinu-live/tests/test_pre_live_scenarios.py`
deliberately bypassed the LLM. This is where that gets closed.

Planned shape, one subfolder per scenario, plus one shared module at the
top level:

```
_scenario_helpers.py <- shared by every scenario: the sys.path/vinu_agent
                         import setup, ScriptedLLM, _call, _tool_history,
                         the mandate-cap constants, and the
                         _assert_no_ungrounded_claims() check that reads
                         AgentLoop's real FactAuditor output
01_clear_uptrend_signal/
  prompt.md          <- exact input given to the agent
  expected.md         <- what a correct response must contain/do
  test_scenario.py     <- asserts the agent's actual tool calls/behavior
                          match, not exact wording (LLM output isn't
                          deterministic run to run -- checks behavior:
                          right tool called, mandate limits respected,
                          refuses when data is missing, etc.)
```

Each scenario's stub `submit_order` tool enforces that scenario's own
expected.md rule directly (mandate cap in 01, evidence-gate in 02,
price-provenance in 03, shock-aware cap in 04, pilot-cap-while-conflict
in 05) and rejects a bad script itself, rather than a test computing
after the fact whether the script "would have" been a violation. None of
these guards are the real `OrderGuard` (which needs a live broker/mandate
file and isn't exercised here) -- each is commented in its stub as a
test-harness stand-in for that one scenario's rule.

Grounding is checked via the real `FactAuditor` (`vinu_agent/audit/
fact_audit.py`), which `AgentLoop` already runs on every completed turn
and returns as `result["audit"]` -- every scenario's tests now assert on
it via `_assert_no_ungrounded_claims`. Note a real gap this surfaced:
`trade_tool.py` echoes a submitted `limit_price` straight back into its
own tool result, so `FactAuditor` verifies a fabricated price the instant
it's submitted as an order argument (see `03_missing_data`'s
`test_guessed_price_order_is_detected_as_violation`, which documents this
concretely). That check still catches everything else -- prices from
`get_stock_price`, share/pct claims with no tool backing -- so it's worth
keeping everywhere, but it is not a defense against a guessed price that
gets submitted as an order.

Each scenario still only runs against a `ScriptedLLM`, never a real
model call -- that's the next gap to close, not yet started.

Candidate scenarios discussed, not yet built:
- Clear uptrend signal — BUILT as `01_clear_uptrend_signal/` (prompt.md,
  expected.md, test_scenario.py: 3 behavior tests pass on the real
  `AgentLoop`: within-mandate buy + grounding, oversized reject,
  missing-data refusal)
- Ambiguous / mixed signals — BUILT as `02_ambiguous_mixed_signals/`
  (prompt.md, expected.md, test_scenario.py: 3 behavior tests pass on
  the real `AgentLoop`: hold on conflicting evidence, price-only buy
  flagged as violation, no order when news unavailable)
- Missing data -- should say so, not guess — BUILT as
  `03_missing_data/` (prompt.md, expected.md, test_scenario.py: 3
  behavior tests pass on the real `AgentLoop`: refuse with no order,
  one retry allowed, guessed-price order flagged as violation)
- Extreme volatility -- should hesitate — BUILT as
  `04_extreme_volatility/` (prompt.md, expected.md, test_scenario.py: 3
  behavior tests pass on the real `AgentLoop`: hold on shock bar,
  reduced-size starter acceptable, full-size chase flagged)
- Conflicting news vs. technicals — BUILT as `05_news_vs_technicals/`
  (prompt.md, expected.md, test_scenario.py: 3 behavior tests pass on
  the real `AgentLoop`: hold naming both sides, pilot-size acceptable,
  technicals-only full buy flagged)

All 5 planned LLM scenarios are now built (01–05), 15 behavior tests
total, all passing on the real `AgentLoop`.

Awaiting direction on which to build first.
