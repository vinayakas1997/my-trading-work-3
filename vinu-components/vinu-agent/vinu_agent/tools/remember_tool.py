import json
from ..agent.tools import BaseTool


class RememberTool(BaseTool):
    name = "remember"
    description = "Save an important finding or data point to persistent cross-session memory"
    parameters = {
        "name": {"type": "string", "description": "A short unique name for this memory (e.g., aapl-momentum-decay)"},
        "content": {"type": "string", "description": "The finding or data to remember"},
        "memory_type": {
            "type": "string",
            "description": "Type: finding, strategy, config, user_pref (default: finding)",
        },
    }
    is_readonly = False

    def execute(self, **kwargs) -> str:
        memory = getattr(self, "_persistent_memory", None)
        if memory is None:
            return json.dumps({"status": "error", "error": "Persistent memory not available"})
        try:
            memory.add(
                name=kwargs["name"],
                content=kwargs["content"],
                memory_type=kwargs.get("memory_type", "finding"),
            )
            return json.dumps({"status": "ok", "name": kwargs["name"]})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
