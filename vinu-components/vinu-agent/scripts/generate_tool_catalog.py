"""Generate a catalog of every registered vinu-agent tool from the real
BaseTool subclasses — same precedent as
vinu-tools/scripts/generate_yaml_catalog.py, adapted to introspect live
Python classes directly (BaseTool subclasses are already structured,
typed classes, not metadata embedded in docstrings/comments the way
vinu-tools' alpha factors are — so this imports and reads class
attributes directly rather than AST-parsing source text).

Usage:
    python scripts/generate_tool_catalog.py

Output:
    vinu-agent/skills/vinu-tools-catalog/tools.yaml
    (agent_tools section only — the services section in that file is
    hand-maintained; this script never touches it, see SKILL.md)
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_VINU_AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_VINU_AGENT_ROOT))

OUTPUT_PATH = _VINU_AGENT_ROOT / "skills" / "vinu-tools-catalog" / "tools.yaml"

_AGENT_TOOLS_KEY = "agent_tools"
_SERVICES_KEY = "services"


def _extract_tool_entry(cls: type) -> dict:
    return {
        "name": cls.name,
        "description": cls.description,
        "parameters": cls.parameters or {},
        "is_readonly": bool(cls.is_readonly),
        "module": f"{cls.__module__}",
    }


def generate_agent_tools() -> dict:
    from vinu_agent.tools import _discover_subclasses

    subclasses = _discover_subclasses()
    catalog = {}
    for cls in sorted(subclasses, key=lambda c: c.name):
        catalog[cls.name] = _extract_tool_entry(cls)
    return catalog


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}

    agent_tools = generate_agent_tools()

    # services section is entirely hand-maintained (substep 2 — these
    # aren't Python classes an introspection script can read) — preserved
    # verbatim across regenerations, never auto-generated.
    services = existing.get(_SERVICES_KEY, {})

    output = {
        _AGENT_TOOLS_KEY: agent_tools,
        _SERVICES_KEY: services,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        yaml.dump(
            output,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=100,
        )

    print(f"{len(agent_tools)} agent tools written to {OUTPUT_PATH}")
    print(f"{len(services)} service entries preserved (hand-maintained, not regenerated)")


if __name__ == "__main__":
    main()
