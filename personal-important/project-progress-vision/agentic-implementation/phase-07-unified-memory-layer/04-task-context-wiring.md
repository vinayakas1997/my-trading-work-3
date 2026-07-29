# Task 4: Wire Unified Memory into Agent Context Builder

**Status:** DONE

## Purpose

Automatically inject symbol-relevant memory entries into the agent's system prompt context — so the agent already "knows" about a symbol's research history, active strategies, and price data before it starts working.

## Approach

- `ContextBuilder.build_messages()` now:
  1. Extracts stock symbols (uppercase 1-5 letter words) from the user's message
  2. For each symbol, calls `UnifiedMemoryStore.list_by_symbol()` to get the top 5 entries
  3. Injects them as `<memory symbol=SYM>` blocks before the user message
  4. Keeps the existing `PersistentMemory.find_relevant()` behavior as a fallback
- `SessionService._run_with_agent()` passes `unified_memory` to both `build_registry` and `ContextBuilder`
- `AgentService` creates a `UnifiedMemoryStore` at `{memory_dir}/../unified_memory.db` and wires it into `SessionService`

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-agent/vinu_agent/agent/context.py` | 36-125 | Modified — added `_extract_symbols()`, unified memory injection in `build_messages()`, `unified_memory` param |
| `vinu-agent/vinu_agent/session/service.py` | 15-33 | Modified — added `unified_memory` param, passes it to build_registry + ContextBuilder |
| `vinu-agent/vinu_agent/service.py` | 1-94 | Modified — creates UnifiedMemoryStore, passes to SessionService, exposes `.unified_memory` property |

## Verification

- [ ] ContextBuilder._extract_symbols finds valid stock tickers in user message
- [ ] Symbol-relevant memory entries are injected as XML-tagged blocks above user message
- [ ] Service creates UnifiedMemoryStore on init
- [ ] unified_memory property is accessible on AgentService
- [ ] No regression: PersistentMemory still works for backward compat
