---
name: agent-self
description: The agent's own identity, capabilities, architecture, and configuration reference
category: system
---

## Agent Identity

I am **Vinu-Agent**, an AI-powered quantitative trading research assistant.

### Architecture
- **ReAct Loop**: Plan → Tool Call → Observe → Repeat, up to 50 iterations
- **Context Management**: 3-tier (microcompact at 50%, collapse at 70%, auto-compact at 128k tokens)
- **LLM Provider**: Configurable (OpenAI, DeepSeek, Anthropic, Ollama via `VINU_LLM_PROVIDER`)
- **Event System**: SSE-based real-time progress events via EventBus
- **Swarm Mode**: Multi-agent DAG orchestration with 4+ presets

### Tools Available
- `backtest`, `get_market_data`, `get_stock_news`, `web_search`
- `load_skill`, `remember`, `search_sessions`, `query_memory`, `compact`
- `plan_workflow`, `complete_step`
- `get_fundamentals`, `analyze_correlation`, `compute_features`
- `evaluate_strategy`, `generate_report`

### Skills Library
Domain-specific skills covering strategy development, factor/risk/technical/
fundamental/macro analysis, and system-level references like this one —
see `vinu-agent/skills/` for the current set. Skills are a **knowledge
library the agent composes at runtime, not scripts that run for it** — see
`00-overview.md` in `steps-to-implement-plan-2/` for the operating
principle behind this.

### How skills and workflow tools actually work at runtime (Step 06, D6)

`load_skill(name)` returns a skill's full `SKILL.md` content on demand —
skills are **not** pre-loaded into the system prompt; the agent calls
`load_skill` only for skills relevant to the task at hand, avoiding the
20-40k-token cost of loading all of them upfront (see Step 06's "Open
risks" for why Option A — preload everything — was rejected in favor of
this on-demand approach).

For multi-skill tasks, the agent can call `plan_workflow(skills=[...])`
first to declare an ordered plan, then `complete_step()` after finishing
each one. Both operate on a single shared `WorkflowTracker`
(`vinu_agent/agent/workflow.py`) — the *same* instance the loop injects
into every LLM call as a `<workflow>...</workflow>` system block
(`AgentLoop.run()`, `vinu_agent/agent/loop.py`), so progress made via
`complete_step` is visible to the agent on its very next turn, not just
recorded silently. This is wired in `session/service.py::_run_with_agent`:
one `WorkflowTracker()` is constructed, passed into `build_registry(...)`
so the tools can update it, and also assigned directly onto the
`AgentLoop` instance so the loop reads the same object it's updating.

**This entire path was broken until Step 06's DI bug fix.**
`build_registry()` (`vinu_agent/tools/__init__.py`) only injects a
dependency into a tool when the tool already has that attribute *before*
injection (`hasattr(tool, "_x")`). `load_skill`, `remember`,
`search_sessions`, `query_memory`, `complete_step`, and `plan_workflow`
previously only referenced their dependency via `getattr(self, "_x",
None)` inside `execute()`, with no `__init__` declaring a default — so
injection silently never fired in production, and every one of these
tools always returned a "not available" error regardless of what
`service.py` passed in. Fixed by giving each tool an `__init__` that sets
its dependency attribute to `None`, matching the convention already used
by tools like `correlation_tool.py`'s `_services_config = {}`. See
`steps-to-implement-plan-2/06-agent-integration.md`'s AGENTS.md entry for
the full trace, and `tests/test_agent_integration.py` for a regression
test that exercises this exact path end-to-end (real `build_registry()` +
`AgentLoop`, not mocks) so it can't silently regress again.

### Governor — hard limit enforced at the loop; heuristics are agent-composed, not hard-coded

The 50-iteration `max_iterations` cap and its 80%-budget wrap-up nudge
(`vinu_agent/agent/loop.py`) are `governor/SKILL.md`'s **Layer 1 hard
limit** — real, enforced in code (`while iteration < self.max_iterations`),
confirmed by that skill's own text. **Layer 2's adaptive heuristics
(progress, expectancy) are deliberately not loop-level code** — per
`governor/SKILL.md`, they're logic the agent itself applies by reading the
hypothesis/evidence trail through existing tools
(`query_hypotheses`/`add_hypothesis_evidence`), consistent with this
project's "skills are a knowledge library, not scripts" principle. Do not
read the absence of a `governor.py` module enforcing Layer 2 as a bug —
it's the intended design, already documented before this step.

### Limitations
- No live trading execution (shadow account / paper mode only)
- Backtesting uses historical data with standard slippage models
- No direct broker connectivity (planned)
- LLM context window limited to 128k tokens before compaction
