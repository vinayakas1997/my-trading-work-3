---
name: 05-tool-catalog
status: Done
phase: 2
code: B3
depends_on: []
unlocks: []
---

# Step 05 — Tool Catalog

## Why this step

The agent's own reasoning about "which tool should I call for this" has no
grounded reference today — it either knows a tool from having called it
before, or guesses. Nothing in `vinu-agent/skills/` describes what the 19
registered tools (`vinu_agent/tools/*.py`) or the underlying `vinu-*`
services actually do, take, or return. This is the "hub of what tools are
present" piece from the original self-agentic description, and it's
confirmed genuinely missing — nothing else in the repo covers it.

## What we're achieving

A catalog the agent can consult to choose between tools/services with
grounded information instead of guessing — ideally **generated from code**,
following the precedent already set by `vinu-tools/scripts/generate_yaml_catalog.py`,
rather than hand-written and left to drift stale.

## Where it matters in the future

Every step in this plan that adds new tools (Step 02 especially) makes this
catalog more valuable and more necessary — a growing tool surface with no
catalog is exactly the situation that produces guessed, wrong tool calls.
This should ideally be built to auto-refresh, so it never goes stale as
Step 02's new tools land.

## How it connects to other steps

- **Independent** — no dependencies, can be built any time.
- **Loosely feeds everything downstream**, in the sense that a well-grounded
  agent makes better decisions in every other step, but nothing else
  structurally blocks on this.
- **Should be revisited after Step 02** — not a hard dependency, but Step
  02 adds new tools this catalog needs to include; if built before Step 02,
  schedule a refresh afterward (this is exactly the kind of thing an
  auto-generated catalog handles for free).

## Substeps

1. Decide the generation approach: a small script that introspects every
   `BaseTool` subclass in `vinu_agent/tools/` (reading `name`, `description`,
   `parameters`, `is_readonly` off each class) and emits a `tools.yaml` —
   modeled on `vinu-tools/scripts/generate_yaml_catalog.py`'s pattern.
2. For the underlying `vinu-*` *services* (not just the agent's own tools)
   — simulator, research, portfolio, strategy, initial-analysis, news,
   live — write a short, hand-maintained entry per service (purpose,
   base URL config key, key endpoints) since these aren't Python classes
   the same introspection trick can read directly. Keep this list short and
   accurate rather than exhaustive.
3. Create `skills/vinu-tools-catalog/SKILL.md` (how to read/choose from the
   catalog) + `tools.yaml` (the generated + hand-maintained content from
   substeps 1–2).
4. Wire the generation script into wherever the project's routine
   maintenance happens (even just "run this before committing a new tool")
   so it doesn't silently go stale the way a hand-written one would.

## What was actually built

**Generation approach differs from `vinu-tools`' precedent in one
respect, deliberately:** `generate_yaml_catalog.py` AST-parses source text
because alpha factors embed metadata in a `__alpha_meta__` dict inside
otherwise-arbitrary files. `BaseTool` subclasses don't need that — `name`,
`description`, `parameters`, `is_readonly` are already plain class
attributes, the exact ones `ToolRegistry`/`build_registry()` reads to
build the LLM's real function-calling schema. `generate_tool_catalog.py`
imports and reads them directly via the existing
`vinu_agent.tools._discover_subclasses()` machinery — guaranteeing the
catalog can never drift from what the agent's tool-calling schema
actually contains, since it's reading the identical source of truth.

**Files created:**
- `vinu-components/vinu-agent/scripts/generate_tool_catalog.py` — run
  from `vinu-agent/`, regenerates only the `agent_tools` section.
- `project-understanding/skills/vinu-tools-catalog/SKILL.md` — explains
  the two-section split and which one is safe to hand-edit.
- `project-understanding/skills/vinu-tools-catalog/tools.yaml` —
  `agent_tools` (29 entries — more than the 26 tool files, since a few
  files register multiple `BaseTool` subclasses, e.g. `trade_tool.py`,
  `hypothesis_write_tools.py`, `run_sweep_candidate_tool.py`) generated
  from real classes; `services` (all 7 `vinu-*` services, plus
  `vinu_stock_price` and `vinu_tools` since they're also real, callable
  services even though not named among the original "7") hand-written
  from direct source reads already done across this session — not
  guessed from names or docs.
- `vinu-components/vinu-agent/tests/test_generate_tool_catalog.py` (3
  tests) — confirms the generator finds a known new tool
  (`run_sweep_candidate`) with the right shape, correctly reflects
  `is_readonly`, and every entry has all required fields.

**Service-entry accuracy note, carried over honestly rather than
smoothed:** `vinu_initial_analysis` and `vinu_stock_price` entries are
intentionally thin — their routes weren't independently re-verified in
this session (unlike `vinu_research`/`vinu_simulator`/`vinu_strategy`/
`vinu_news`/`vinu_portfolio`, all read in full at some point across Steps
01-09), and the entries say so explicitly rather than presenting
guessed endpoint lists as fact. `vinu_live` is documented as **not**
reachable from any current agent tool (confirmed: absent from
`vinu_agent/config.py`'s `services` dict) — consistent with Step 09's
finding that `ShadowEvaluator` there is real but unwired.

**Regeneration discipline:** documented as a manual step (`python
scripts/generate_tool_catalog.py` before considering a tool-adding change
done) — no pre-commit/CI hook wires this automatically yet, and
`SKILL.md` says so plainly rather than overclaiming automation that
doesn't exist. Wiring an automatic hook is flagged as a real follow-up,
not silently assumed done.

## Definition of done

- [x] Generation script exists and produces `tools.yaml`'s `agent_tools`
      section from the real `BaseTool` subclasses — verified: ran it,
      confirmed 29 real tools with correct shape via both a direct
      script run and 3 passing tests.
- [x] Service-level entries written for all 7 original `vinu-*` services
      (plus 2 more found to be equally real and callable) — accuracy
      honestly scoped to what was actually re-verified this session.
- [x] `SKILL.md` explains how to read and choose from the catalog,
      including which section is safe to edit and which isn't.
- [x] Regeneration step identified and documented (`python
      scripts/generate_tool_catalog.py`) — not yet wired into CI/pre-commit;
      stated as a known gap, not implied as solved.
