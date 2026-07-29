# Phase 4 — Context-Efficient Retrieval for Agents/Skills/Tools

Status: **not started** · Depends on: Phase 3 · Blocks: —

## What it is

The payoff phase: changes how `vinu-agent`'s agent loop, skills, and tools actually consume the
memory layer from Phase 3, so the investment in catalogs/watermarks translates into fewer
redundant LLM calls and smaller, more precise prompts — not just cleaner infrastructure nobody
uses differently.

Two concrete inefficiencies exist today that this phase targets directly:

1. **Redundant LLM calls that a freshness check could avoid.** `vinu-research/vinu_research/loop.py`'s
   `_characterize_stock` (lines ~850-918) runs a full LLM call to characterize a stock's
   volatility/trend/RSI behavior on *every single research run* for that symbol, regardless of
   whether market conditions have meaningfully changed since the last time it was characterized
   a day/week ago. With Phase 3's `price_data_through`/freshness stamps available, this becomes
   a cheap check: "was this symbol characterized within the last N days on data that's still
   current? If so, reuse the cached conclusion instead of re-calling the LLM."
2. **Context bloat from re-reading history instead of querying a summary.** The agent's context
   currently gets built from things like full skill descriptions (`vinu-agent/vinu_agent/agent/context.py`)
   and, when a task needs research history, from re-reading markdown reports or replaying
   `HypothesisRegistry` JSON. A single `get_memory_state(symbol)` call (Phase 3) replacing that
   re-reading is both fewer tokens and a more precise, structured input for the LLM to reason
   over.

## Impact

**Before this phase:** Phases 1–3 exist as infrastructure, but agent behavior is unchanged —
the same redundant LLM calls and the same "re-read a markdown report to figure out what we
already know" pattern continue.

**After this phase:** Research runs skip redundant characterization calls when cached
conclusions are still fresh (direct cost/latency savings on every run). Agent-facing tools that
need "what do we already know about this symbol" pull a compact structured summary instead of
reconstructing it from scattered files — smaller prompts, more precise grounding, and a
principled way for the agent to recognize when its own knowledge is stale rather than silently
acting on outdated conclusions.

## Where changes occur

- `vinu-research/vinu_research/loop.py` — `_characterize_stock` (lines ~850-918) and any other
  per-run LLM call whose output is a slowly-changing fact about a symbol (not specific to this
  particular strategy attempt) gets a freshness guard: check Phase 3's memory layer for a recent
  cached result before calling the LLM; write the result back with a fresh timestamp when it
  does run.
- `vinu-agent/vinu_agent/agent/context.py` and relevant tools (e.g.
  `vinu-agent/vinu_agent/tools/research_tool.py`, `trade_plan_tool.py`) — wherever a tool
  currently needs "prior context for this symbol," prefer a Phase 3 `get_memory_state()` call
  over re-reading `report_md`/`HypothesisRegistry` files directly. Skills
  (`vinu-agent/skills/*/SKILL.md`) that reference "check prior research" should be updated to
  point at this query pattern rather than "go read the report."
- New skill or extension to an existing one (e.g. `research-discipline`) documenting the
  freshness-check pattern itself, so future skill/tool authors follow it rather than defaulting
  to "just call the LLM again" or "just re-read the file."
- `vinu-research/vinu_research/hypothesis_registry.py` — conclusions written here should
  include enough structure (not just prose) that Phase 3's memory layer can surface them as
  `known_failure_modes`/cached facts without an LLM having to re-read and re-summarize them.

## How to test it

- Unit test: `_characterize_stock` is *not* called (mock asserts zero invocations) when a fresh
  cached characterization exists in the memory layer for that symbol within the freshness
  window; *is* called when the cached entry is stale or absent.
- Token/cost regression check: measure prompt size and LLM call count for a research run against
  a symbol with substantial prior history, before and after this phase, and confirm a measurable
  reduction — this is the concrete metric that proves the investment paid off, not just "code
  looks cleaner."
- Correctness test: confirm that when the freshness guard skips a re-characterization, the
  reused cached result is actually used downstream (not silently discarded), and that results
  are unchanged from the always-recompute path when the cache happens to be fresh.
- Staleness-detection test: seed a scenario where cached data is deliberately stale (freshness
  window exceeded) and confirm the guard correctly falls through to a fresh LLM call rather than
  serving outdated data.
