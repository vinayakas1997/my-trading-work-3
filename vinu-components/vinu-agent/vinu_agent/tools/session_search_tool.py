import json
from ..agent.tools import BaseTool


class SessionSearchTool(BaseTool):
    name = "search_sessions"
    description = "Search across all past conversation sessions using full-text search"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query text"},
        },
        "required": ["query"],
    }
    is_readonly = True

    def __init__(self):
        self._session_service = None

    def execute(self, **kwargs) -> str:
        session_service = getattr(self, "_session_service", None)
        if session_service is None:
            return json.dumps({"status": "error", "error": "Session service not available"})
        try:
            results = session_service.search(kwargs["query"])
            return json.dumps({"status": "ok", "results": results[:10]})
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
