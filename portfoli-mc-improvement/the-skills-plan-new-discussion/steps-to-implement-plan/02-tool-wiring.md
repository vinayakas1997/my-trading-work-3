---
name: 02-tool-wiring
status: Done
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

## What was actually built

Four new read-only `vinu-agent` tools, plus the backend routes needed to
back them (three of the four data sources had no HTTP surface at all
before this step):

- **`query_hypotheses`** → new route `GET /research/hypotheses`
  (`vinu_research/server/routes_introspect.py`), wraps
  `HypothesisRegistry.query_by_symbol`/`list_all`. Real, populated data —
  `service.py` already writes to this registry during every research run.
- **`check_symbol_research_state`** → new route
  `GET /research/symbols/{symbol}/state`, wraps
  `ResearchStorage.is_symbol_exhausted` + `get_catalog_entry`.
- **`get_run_checkpoints`** → new route
  `GET /research/runs/{run_id}/checkpoints` (with `latest_only`), wraps
  `ResearchStorage.list_checkpoints`/`get_last_checkpoint`. Per Step 01's
  finding, this is the **first real consumer** of checkpoint data — nothing
  else reads it back yet.
- **`get_backtest_validation`** → **no new backend route needed.** The
  `validation` block (the 7-test statistical verdict) was already returned
  by vinu-simulator's existing `GET /simulator/results/{run_id}` route; the
  tool calls it and strips `equity`/`trades` locally so the agent doesn't
  receive a huge payload just to read the verdict. This confirms Step 06's
  substep-4 speculation that some of this might already exist.

**`query_judgment_history` was deliberately NOT built.** `JudgmentStore`
(the class meant to back "was my past verdict correct") was found to be
**completely unwired** — grepped across all of `vinu-research`, it's
instantiated nowhere outside its own test file. No code ever calls
`.record()`. Building a query tool over a store nothing writes to would be
exactly the "knowledge without reach" problem this step exists to fix, in
the other direction — visibility into permanently-empty data. Wiring
`JudgmentStore.record()` into `loop.py`'s verdict path is real work but is
a *behavior change* to the research loop, not tool visibility — it belongs
to whichever step next touches `loop.py`'s critic/verdict logic (most
likely Step 07 or 08), not this one.

**Bug found and fixed in passing:** `research_tool.py` (the existing
`run_research` tool) was posting to `{url}/run` instead of
`{url}/research/run` — confirmed via its own test suite, which asserted
the `/research/run` path and was consequently failing (`2 failed, 4
passed` before the fix). Since every new tool in this step needed to get
this exact same prefix convention right, the one-line fix was made
alongside them; verified by re-running the suite (`6 passed`).

**Open finding, not resolved here:** other multi-service tools
(`trade_plan_tool.py`, `portfolio_comparison_tool.py`) construct URLs
against six different services (`vinu_initial_analysis`, `vinu_tools`,
`vinu_simulator`, `vinu_stock_price`, `vinu_news`, `vinu_research`) and
were not individually checked for the same missing-route-prefix pattern.
A dedicated audit is recommended but is out of this step's scope.

## Definition of done

- [x] Tool list decided and each mapped to a confirmed, real backend
      endpoint (not an assumed one) — `get_backtest_validation` turned out
      to need no new endpoint at all.
- [x] Each tool implemented, registered, and covered by a passing test —
      4 new tools, 4 new test files, all passing; confirmed auto-discovered
      by `build_registry()`.
- [x] Manually verified: ran the new routes end-to-end via FastAPI's
      `TestClient` against a real `HypothesisRegistry` (temp-file backed)
      and a mocked `ResearchService.storage` — all three new
      `vinu-research` routes returned real, correctly-shaped data.
      `get_backtest_validation` was verified structurally (test coverage)
      but not against a live `vinu-simulator` instance — flagged for
      whoever first runs this against the real running service.
