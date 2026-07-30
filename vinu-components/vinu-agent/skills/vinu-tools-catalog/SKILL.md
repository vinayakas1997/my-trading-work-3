---
name: vinu-tools-catalog
description: What every registered vinu-agent tool and every vinu-* service actually does, takes, and returns — the "hub of what's present" reference so tool choice is grounded instead of guessed.
category: reference
---

## Tool Catalog — What's Actually Available

`tools.yaml` has two sections, generated and maintained differently —
don't confuse them:

### `agent_tools` — generated, never hand-edited

Every entry here is produced by
`vinu-agent/scripts/generate_tool_catalog.py` introspecting the real
`BaseTool` subclasses in `vinu_agent/tools/*.py` directly (their actual
`name`, `description`, `parameters`, `is_readonly` — the same attributes
`ToolRegistry` uses to build the LLM's function-calling schema, so this
catalog can never describe a tool differently than the tool actually
behaves). **Regenerate this section any time a tool is added, removed, or
changed** — run `python scripts/generate_tool_catalog.py` from
`vinu-agent/`. Do not hand-edit `agent_tools` entries; they will be
silently overwritten on the next regeneration, and any manual correction
belongs in the tool's own source (`description`/`parameters` on the
class), not here.

### `services` — hand-maintained, preserved across regenerations

The 7 `vinu-*` backend services aren't Python classes an introspection
script can read the same way — each entry here is a short, hand-written
summary (purpose, base URL config key, key endpoints). Keep these
**short and accurate rather than exhaustive** — this is a map for
choosing which service to reach for, not full API documentation (each
service's own `server/routes_*.py` is the actual source of truth for
exact request/response shapes). The generation script preserves this
section verbatim; it is never auto-generated or clobbered by a re-run.

### How to use this catalog

1. Load `tools.yaml` via `load_support_file("tools.yaml")`.
2. Choosing an **agent tool**: scan `agent_tools` for a `name`/
   `description` match. Check `is_readonly` before calling anything that
   mutates state (`is_readonly: false`) — confirm that's actually
   intended, not incidental.
3. Choosing a **service** to build a new tool against, or to understand
   what's reachable at all: scan `services` for the right base URL and
   starting endpoint, then read that service's own `routes_*.py` for the
   exact contract before writing code against it — this catalog gets you
   to the right file, it doesn't replace reading it.
4. If neither section has what you need, say so explicitly — this
   catalog reflects real, current state; a gap here is a real gap, not a
   documentation oversight to work around by guessing.

### Keeping this from going stale

Regenerate `agent_tools` as part of adding any new tool — treat an
un-regenerated catalog after a tool change the same as a failing test:
something that should be fixed before considering the change done. There
is currently no automated hook enforcing this (no pre-commit/CI wiring
exists yet for it) — until one does, this is a manual discipline, not a
guarantee. If a `Step 02`-style tool-adding step lands without a
regeneration, treat that catalog as stale until confirmed otherwise.
