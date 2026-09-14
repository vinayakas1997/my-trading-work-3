# Situation 4: does my own #6 symbol-grounding fix actually work through the real pipeline, not just its own unit tests?

## Question

The #6 fix (`research-discussion-v2/fixes-log.md`) added `_grounding_context`
plumbing across `AgentLoop`, `_process_tool_calls`, and `TradeTool`. The unit
tests for it either set `tool._grounding_context` by hand or used a stand-in
`GroundingAwareWriteTool` — real, but not the same as proving the actual
`TradeTool` class, wired through the actual `AgentLoop.run()` →
`ToolRegistry` → tool-execution path a real deployment uses, behaves
correctly in the exact motivating scenario the fix was built for.

## Where

`vinu-agent/vinu_agent/agent/loop.py` (`AgentLoop.run`, `_process_tool_calls`)
+ `vinu-agent/vinu_agent/tools/trade_tool.py` (`TradeTool.execute`).

## How tested

Real `AgentLoop`, real `ToolRegistry`, real `TradeTool` instance registered
into it exactly as production does. Only the broker, `OrderGuard`, and
`TradingMandate.load()` were mocked (the same boundary every existing
`trade_tool.py` test mocks at) — the actual grounding logic, the actual
`_process_tool_calls` wiring, and the actual `AgentLoop.run()` loop are all
real code, driven by a scripted LLM through `loop.run([...])`.

**Scenario A** (the failure mode #6 exists for): user asks about MSFT; the
LLM's tool call submits an order for AAPL — never mentioned anywhere in this
turn.

**Scenario B** (control): user explicitly asks to buy AAPL; the LLM submits
AAPL.

## Observed

Scenario A — held for confirmation, not silently traded and not flat-out
rejected:

```json
{
  "status": "pending_confirmation",
  "message": "AAPL does not appear anywhere in this turn's request or the tool results used to resolve it -- confirm this is the intended symbol before it trades. (A company name resolved to the wrong ticker, or a symbol carried over from earlier in a long conversation, are both easy mistakes to make.)",
  "reason_code": "symbol_not_grounded",
  ...
}
```

Scenario B — submitted normally, no friction for a correctly-grounded order:

```json
{
  "status": "submitted",
  "order_id": "o1",
  "symbol": "AAPL",
  ...
}
```

## Verdict: fix confirmed working end-to-end, as designed

Matches intent exactly — this is the difference between "the unit tests for
my own fix pass" and "an auditor drove the real pipeline with a realistic
scripted conversation and watched the right thing happen." Worth the extra
step precisely because it's my own fix under review, not someone else's —
the same scrutiny applies either way.
