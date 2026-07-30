---
name: 05-tool-catalog
status: Not Started
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

## Open risks / assumptions

- The auto-generation approach only covers the agent's own tools cleanly;
  the service-level entries (substep 2) will need manual upkeep discipline
  since there's no single source to introspect for those.

## Definition of done

- [ ] Generation script exists and produces `tools.yaml` from the real
      `BaseTool` subclasses.
- [ ] Service-level entries written for all 7 `vinu-*` services.
- [ ] `SKILL.md` explains how to read and choose from the catalog.
- [ ] Regeneration step identified/wired so this doesn't go stale the next
      time a tool is added.
