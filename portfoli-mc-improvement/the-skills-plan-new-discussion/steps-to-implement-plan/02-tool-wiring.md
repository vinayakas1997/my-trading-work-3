---
name: 02-tool-wiring
status: Not Started
phase: 1
code: A2
depends_on: []
unlocks: [03-gatekeepers-skill, 08-governor]
---

# Step 02 — Tool Wiring

## Why this step

This is the single most important step in the whole plan — everything else
in Phase 2 and 3 assumes it's done. Right now, `vinu-agent`'s only way to
touch the rich research backend is `research_tool.py`'s `run_research`,
which fires one blocking HTTP POST to `/run` and returns raw text. Nothing
lets the agent inspect `HypothesisRegistry` entries, read an
`iteration_checkpoint`, check whether a symbol is exhausted, or see the
`validation` block (the 7-test statistical verdict) on a specific backtest
result. Writing a skill that says "read the hypothesis evidence before
concluding" is dishonest to the agent if no tool exists for it to actually
do that. **Knowledge without reach is not knowledge the agent can act on.**

## What we're achieving

A small set of new (or extended) `vinu-agent` tools that expose, read-only
at minimum, the state that already exists:

- Query past hypotheses and their evidence (reasoning + conclusion per
  iteration) for a symbol/strategy — backed by `HypothesisRegistry`.
- Query `JudgmentRecord` history, including `verdict_correct`, for a symbol.
- Read/list `iteration_checkpoints` for a given run — for resuming a search
  across sessions rather than assuming one uninurrupted loop.
- Check `is_symbol_exhausted` before starting new work on a symbol.
- Read the full `validation` block (monte-carlo p-value, block-bootstrap,
  price-path, walk-forward consistency, bootstrap CI, BCa CI, placebo) for
  a specific backtest result, not just the top-line metrics.

## Where it matters in the future

Every step past this one either directly calls these tools or writes skill
text that assumes they exist. If Step 02 is incomplete, Step 03's
`gatekeepers` skill has nothing real to point the agent at, and Step 08's
governor has no way to check exhaustion/checkpoint state — both would be
paper designs with no way to actually run.

## How it connects to other steps

- **Depends on Step 01** for the exact schema/behavior of
  `iteration_checkpoints`, `is_symbol_exhausted`, and whether FTS5 already
  exists — get those answers before finalizing tool parameter shapes here,
  so the tools match reality on the first attempt instead of needing a
  rewrite.
- **Unlocks Step 03** — the `gatekeepers` skill needs a tool that returns
  the `validation` block and PBO/correlation-gate/promotion results; it
  cannot be written honestly before this exists.
- **Unlocks Step 08** — the governor's hard-limit and progress-heuristic
  layers need to read checkpoint/exhaustion state to make a real decision,
  not a hypothetical one.

## Substeps

1. Decide the tool boundary: new standalone tools (e.g. `query_hypotheses`,
   `get_backtest_validation`, `check_symbol_exhaustion`) vs. extending
   `research_tool.py` with optional query modes. Prefer new, narrowly-scoped
   tools — `run_research`'s job (trigger the loop) is different in kind from
   these (inspect state), and conflating them makes both harder to reason
   about.
2. For each new tool, confirm the underlying service already exposes the
   data over HTTP (check `vinu-research/vinu_research/server/routes_*.py`
   and `vinu-simulator/vinu_simulator/server/routes_*.py`) — if a route
   doesn't exist yet for something this step needs, that's a small new
   route to add on the service side, not just a new tool on the agent side.
3. Implement each tool following the existing `BaseTool` pattern (see
   `vinu_agent/tools/research_tool.py` and `load_skill_tool.py` for the
   shape: `name`, `description`, `parameters`, `is_readonly`, `execute`).
   Mark all of these `is_readonly = True` — this step is about visibility,
   not action.
4. Register each new tool wherever `research_tool.py` currently gets
   registered (find the tool registry / tool list construction point).
5. Write a short test per tool (see `vinu-agent/tests/test_research_tool.py`
   as the existing pattern) confirming it returns real data against a
   running (or mocked) service.

## Open risks / assumptions

- Assumes the underlying services (`vinu-research`, `vinu-simulator`)
  already expose this data over their HTTP APIs. If they only compute it
  internally and never return it in a response, this step's scope grows to
  include adding those routes — check this early, in substep 2, before
  committing to a tool list.
- Depends on Step 01's FTS5 finding — if FTS5 doesn't exist yet, add it here
  (this is the natural place, since it's part of exposing hypothesis/reasoning
  text for search) rather than inventing a separate storage step.

## Definition of done

- [ ] Tool list decided and each mapped to a confirmed, real backend
      endpoint (not an assumed one).
- [ ] Each tool implemented, registered, and covered by a passing test.
- [ ] Manually verified: an agent session can call each new tool and get
      back real data from a real (or realistically mocked) backend — not
      just that the code compiles.
