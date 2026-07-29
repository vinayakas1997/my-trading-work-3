# Task 3: Create query_memory Agent Tool

**Status:** DONE

## Purpose

Give the agent a `query_memory` tool to search the unified memory catalog — research runs, simulation results, price data, news articles, and stored findings — from within a conversation.

## Approach

- `QueryMemoryTool` extends `BaseTool` with `is_readonly = True`
- Parameters: `query` (text search), `symbol`, `source`, `memory_type`, `limit`
- Delegates to `UnifiedMemoryStore.search()` under the hood
- Returns structured JSON with status, count, and results array
- Also updated `RememberTool` to route through `UnifiedMemoryStore` instead of file-based `PersistentMemory`, and added a `symbol` parameter for richer tagging
- `build_registry` in `tools/__init__.py` now injects `_unified_memory` into tools that have the attribute

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-agent/vinu_agent/tools/query_memory_tool.py` | 1-53 | Created — QueryMemoryTool |
| `vinu-agent/vinu_agent/tools/remember_tool.py` | 1-42 | Modified — routes through UnifiedMemoryStore, added symbol param |
| `vinu-agent/vinu_agent/tools/__init__.py` | 26-60 | Modified — build_registry injects `_unified_memory` |

## Verification

- [ ] query_memory tool auto-discovered and registered by build_registry
- [ ] query_memory with query text returns FTS-ranked results
- [ ] query_memory with symbol filter works
- [ ] query_memory with source/memory_type filters work
- [ ] remember_tool writes to unified store with symbol tag
