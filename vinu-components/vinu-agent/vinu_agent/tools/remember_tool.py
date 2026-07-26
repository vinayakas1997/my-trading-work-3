from __future__ import annotations

import json
from ..agent.tools import BaseTool
from ..memory.unified_store import MemoryEntry, _now


class RememberTool(BaseTool):
    name = "remember"
    description = "Save an important finding or data point to persistent cross-session memory"
    parameters = {
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
    }
    is_readonly = False

    def execute(self, **kwargs) -> str:
        unified = getattr(self, "_unified_memory", None)
        if unified is None:
            return json.dumps({"status": "error", "error": "Unified memory not available"})
        try:
            entry = MemoryEntry(
                id=f"agent-{kwargs['name']}",
                source="agent",
                source_id=kwargs["name"],
                symbol=kwargs.get("symbol", ""),
                memory_type=kwargs.get("memory_type", "finding"),
                title=kwargs["name"],
                content=kwargs["content"],
                summary=kwargs["content"][:200],
                created_at=_now(),
                updated_at=_now(),
            )
            unified.add_entry(entry)
            return json.dumps({"status": "ok", "name": kwargs["name"]})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
