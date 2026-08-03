---
name: research-run-null-user-idea-crash
status: fixed
severity: crashes-the-e2e-checklists-own-example-payload
---

# Bug: `POST /research/run` crashed on the exact payload `03`'s own checklist documents

## What was wrong

`03-strategy-research-and-simulation.md`'s example curl payload for
`POST /research/run` sends `"user_idea": null`. Sending exactly that
payload for AAPL/TSLA/JNJ returned:

```
{"detail":"'NoneType' object has no attribute 'lower'"}
```

Root cause: `RunResearchRequest.user_idea` (`server/routes_read.py:18`) is
typed `str | None` with the docstring *"If None, auto-proposed from angle
context"* — but `/research/run`'s handler passes `body.user_idea` straight
into `ResearchService.run_research(user_idea: str, ...)`
(`service.py:68`), which is typed as a plain (non-optional) `str` and
immediately does `user_idea.lower()` with no None-check. The "auto-propose
if None" behavior the request model promises only actually existed in the
**separate** `ensure_strategy()` method (used by `/research/ensure`, a
different route with different skip-if-exists semantics) — `run_research()`
itself, the method `/research/run` actually calls, never implemented its
own documented contract.

## Why it mattered

This is the first route call in `03`'s multi-step research/simulation
flow, using the exact payload the checklist itself specifies. Every one of
the 3 tickers failed here, immediately, before any code generation,
backtest, or promotion logic ever ran.

## What was fixed

`vinu_research/service.py`'s `run_research()`: retyped `user_idea` to
`str | None`, and added the same "if None, propose one" resolution
`ensure_strategy()` already had (calling the same `_propose_idea(symbol)`),
raising a clear `ValueError` if proposal also fails, instead of crashing on
`.lower()`. `ensure_strategy()` itself is unaffected — it still resolves
`user_idea` before calling `run_research()`, so the new check inside
`run_research()` is a no-op on that path.

Added `TestRunResearchNoneUserIdea` (`tests/test_service.py`, 2 new
tests): confirms `run_research(None, ...)` calls `_propose_idea` instead of
raising `AttributeError`, and confirms a failed proposal raises a clear
`ValueError` rather than the confusing original crash. Zero coverage of
this path existed before — confirmed by grepping `test_service.py` for
`user_idea`, no hits.

## What was achieved

`POST /research/run` now works with the exact payload
`03-strategy-research-and-simulation.md` documents (`user_idea: null`),
auto-proposing a strategy idea from the symbol's angle context instead of
crashing before any real work starts.
