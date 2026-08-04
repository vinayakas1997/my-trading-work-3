---
name: unified-memory-missing-held-symbols-union
status: fixed
severity: silent-context-gap-for-held-but-unmentioned-positions
---

# Bug: `ContextBuilder`'s long-term-memory block only looked at the current message's symbols, not held positions

## What was wrong

Found by static code review while cross-checking
`04-vinu-components-integration-plan.md`'s claim that `GroundTruthInjector`
correctly avoids `_extract_symbols()`'s "only what's mentioned in today's
message" limitation by reading real broker positions instead. That claim is
true (`vinu_agent/audit/ground_truth.py:28-37` reads
`broker.get_positions()`) — but checking every other consumer of
`_extract_symbols` in `context.py` found one that still has the exact
blind spot the integration plan flagged as a real, named risk.

`ContextBuilder.build_messages()` has four blocks that scope "which symbols
matter this turn" — ground-truth prices, the Facts & Limitations Registry,
`FreshnessChecker`, and the research-digest reader. Three of the four
(`context.py:167`, `189`, `215`) correctly union
`self._held_symbols | self._extract_symbols(user_message)`. The fourth —
the `unified_memory` long-term-recall block (`context.py:247-248`, before
this fix) — used only `self._extract_symbols(user_message)`, with no
`held_symbols` union at all.

Practical effect: if a session holds AAPL but a given turn's message
doesn't happen to mention "AAPL" (e.g. "what's going on in the market
today?"), that turn correctly still gets fresh ground-truth price, facts,
freshness, and research-digest data for AAPL (those four are fixed) — but
AAPL's accumulated long-term memory (past notes, news, research entries
tagged to that symbol via `UnifiedMemoryStore`) silently does not get
recalled into context on that turn, even though it's a currently-held
position.

## Why it mattered

This is the same shape of gap `04-vinu-components-integration-plan.md`
already named as a real, confirmed bug for `_extract_symbols` generally
(the reason `GroundTruthInjector` was deliberately built to avoid it) — it
had just recurred in a different block of the same function, not caught
because the original check only verified the block it was written to fix
(ground-truth), not every other consumer of the same helper in the same
file.

## What was fixed

`vinu-agent/vinu_agent/agent/context.py:248`: changed

```python
symbols = self._extract_symbols(user_message)
```

to

```python
symbols = sorted(set(self._held_symbols) | set(self._extract_symbols(user_message)))
```

— matching the exact pattern already used by the other three blocks.

Added a regression test,
`test_memory_recalled_for_held_but_unmentioned_symbol`
(`vinu-agent/tests/test_integration_context.py`): constructs a
`ContextBuilder` with `held_symbols=["AAPL"]`, seeds a memory entry for
AAPL, sends a user message that never mentions "AAPL," and asserts the
`<memory symbol=AAPL>` block still appears.

**Verified**: `python -m pytest vinu-agent/tests` — 281 passed (280
pre-existing + 1 new), no regressions.

## What was achieved

All four of `ContextBuilder`'s symbol-scoped injection blocks now
consistently include held positions regardless of what a given turn's
message happens to mention — closing the one remaining instance of the
`_extract_symbols` blind spot `04-vinu-components-integration-plan.md`
already flagged as a real risk elsewhere in the same file.
