from typing import Any

from ..agent.tools import BaseTool


class CompactTool(BaseTool):
    name = "compact"
    description = "Explicitly compact the conversation context. Use when the conversation history is long (near context window limits) to preserve key information while reducing token usage."
    parameters: dict = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    is_readonly = True
    repeatable = True

    def execute(self, **kwargs: Any) -> str:
        return '{"status": "ok", "__compact": true, "message": "Context compaction triggered. The conversation history will be compacted on the next iteration."}'
