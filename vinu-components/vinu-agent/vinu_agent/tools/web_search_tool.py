import json
from ..agent.tools import BaseTool


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for current information on a query"
    parameters = {
        "query": {"type": "string", "description": "Search query"},
    }
    is_readonly = True

    def execute(self, **kwargs) -> str:
        try:
            import httpx
            resp = httpx.get(
                "https://api.duckduckgo.com/",
                params={
                    "q": kwargs["query"],
                    "format": "json",
                    "no_html": 1,
                    "skip_disambig": 1,
                },
                timeout=15,
            )
            data = resp.json()
            results = []
            for topic in data.get("RelatedTopics", []):
                if "Text" in topic:
                    results.append({"title": topic.get("Text", ""), "url": topic.get("FirstURL", "")})
            return json.dumps({"status": "ok", "results": results[:10]}, indent=2)
        except Exception as exc:
            return json.dumps({"status": "error", "error": str(exc)})
