# Situation 17: can a plain substring match make my own #6 fix miss a real mismatch?

## Question

The #6 symbol-grounding fix (situation 4 confirmed it works end-to-end for
its main motivating case) checks `symbol not in grounding_context` -- a
plain Python substring test on the uppercased turn text. Many real tickers
are short, common words or word-fragments (`CAT`, `ALL`, `IT`, `GE`, `F`,
`ON`...). If the user's turn happens to contain an ordinary word that
*contains* the ticker as a substring -- discussing "Caterpillar" the
company/word, say -- while the LLM's tool call orders ticker `CAT`, does
the naive substring check wrongly treat `CAT` as "grounded," even though
the ticker itself was never mentioned?

## Where

`vinu-agent/vinu_agent/tools/trade_tool.py::TradeTool.execute()`, the #6
grounding check (`symbol not in grounding_context`).

## How tested

Same real `AgentLoop` → `ToolRegistry` → `TradeTool` harness as situation
4 (only the broker/guard/mandate boundary mocked), with a scripted turn
that only ever says "Caterpillar" -- never the ticker `CAT` -- and an LLM
tool call ordering `CAT`.

```python
run_scenario("What's the outlook for Caterpillar's heavy machinery division this quarter?", "CAT")
```

## Observed (before the fix)

```json
{
  "status": "submitted",
  "order_id": "o1",
  "symbol": "CAT",
  ...
}
```

Silently submitted -- no pause, no confirmation. `"CAT" in "CATERPILLAR'S
HEAVY MACHINERY..."` is `True` in Python, so the check considered it
grounded on the strength of an unrelated word sharing a prefix.

## Verdict: real bug in my own earlier fix, found by testing it, fixed

This is exactly the class of mistake #6 was built to catch (a symbol
resolved incorrectly / carried over without real basis), slipping through
because the check's own string-matching was looser than its stated intent.
**Fixed**: `trade_tool.py` now uses a word-boundary regex
(`_symbol_is_grounded()`, `re.search(rf"\b{re.escape(symbol)}\b",
grounding_context)`) instead of plain `in`. Re-ran the same scenario after
the fix:

```json
{
  "status": "pending_confirmation",
  "reason_code": "symbol_not_grounded",
  ...
}
```

Also re-ran situation 4's original two scenarios (mismatched symbol still
pauses; a correctly-grounded order still submits cleanly) to confirm the
fix didn't regress the main case, and added two permanent regression tests
to `tests/test_trade_tool.py::TestSymbolGroundingCheck`: the Caterpillar/CAT
substring case (must still pause) and a control case where the ticker
appears as its own standalone word (must still submit normally, so the
fix isn't stricter than necessary for the common legitimate case). Full
`test_trade_tool.py` suite: 24 passed.

This is the second real bug found in this audit that traces back to my own
earlier work in this session (situation 15 was the first, in
`order_guard.py`) -- both found by actually driving the code with a
realistic scenario rather than trusting the unit tests written alongside
the original fix.
