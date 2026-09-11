# llm-scenarios-test

Acceptance scenarios for the real LLM agent loop -- the untested layer:
everything checked in `vinu-live/tests/test_pre_live_scenarios.py`
deliberately bypassed the LLM. This is where that gets closed.

Planned shape, one subfolder per scenario:

```
01_clear_uptrend_signal/
  prompt.md          <- exact input given to the agent
  expected.md         <- what a correct response must contain/do
  test_scenario.py     <- asserts the agent's actual tool calls/behavior
                          match, not exact wording (LLM output isn't
                          deterministic run to run -- checks behavior:
                          right tool called, mandate limits respected,
                          refuses when data is missing, etc.)
```

Candidate scenarios discussed, not yet built:
- Clear uptrend signal
- Ambiguous / mixed signals
- Missing data -- should say so, not guess
- Extreme volatility -- should hesitate
- Conflicting news vs. technicals

Awaiting direction on which to build first.
