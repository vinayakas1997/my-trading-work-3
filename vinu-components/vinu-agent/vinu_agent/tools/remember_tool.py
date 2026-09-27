from __future__ import annotations

import json
from ..agent.tools import BaseTool
from ..memory.unified_store import MemoryEntry, _now


class RememberTool(BaseTool):
    name = "remember"
    description = "Save an important finding or data point to persistent cross-session memory"
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "A short unique name for this memory (e.g., aapl-momentum-decay)"},
            "content": {"type": "string", "description": "The finding or data to remember"},
            "symbol": {
                "type": "string",
                "description": "Stock symbol this memory relates to (optional)",
            },
            "memory_type": {
                "type": "string",
                "description": "Type: finding, strategy, config, user_pref (default: finding)",
            },
        },
        "required": ["name", "content"],
    }
    is_readonly = False

    def __init__(self):
        self._unified_memory = None

    def execute(self, **kwargs) -> str:
        unified = getattr(self, "_unified_memory", None)
        if unified is None:
            return json.dumps({"status": "error", "error": "Unified memory not available"})
        try:
            entry_id = f"agent-{kwargs['name']}"
            # `add_entry` upserts by id, so remembering the same `name`
            # twice silently replaces the prior entry -- previously even
            # `created_at` got reset to now, losing when this was first
            # remembered. Preserve the original `created_at` on an
            # overwrite, and tell the caller this replaced something
            # rather than staying silent about it.
            existing = unified.get_entry(entry_id)
            entry = MemoryEntry(
                id=entry_id,
                source="agent",
                source_id=kwargs["name"],
                symbol=kwargs.get("symbol", ""),
                memory_type=kwargs.get("memory_type", "finding"),
                title=kwargs["name"],
                content=kwargs["content"],
                summary=kwargs["content"][:200],
                created_at=existing.created_at if existing is not None else _now(),
                updated_at=_now(),
            )
            unified.add_entry(entry)
            response = {"status": "ok", "name": kwargs["name"]}
            if existing is not None:
                response["overwritten"] = True
            return json.dumps(response)
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
