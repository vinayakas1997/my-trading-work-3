import json
from ..agent.tools import BaseTool


class NewsTool(BaseTool):
    name = "get_news"
    description = "Fetch news articles for a symbol over a date range"
    parameters = {
        "symbol": {"type": "string", "description": "Stock symbol"},
        "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
        "limit": {"type": "integer", "description": "Max articles to return (default: 20)"},
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_news", "http://localhost:8080")
        query = f"{kwargs['symbol']} {kwargs.get('start_date', '')} {kwargs.get('end_date', '')}"
        resp = httpx.get(
            f"{url}/search",
            params={"q": query.strip(), "limit": kwargs.get("limit", 20)},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.text
