import json
from ..agent.tools import BaseTool


class ResearchTool(BaseTool):
    name = "run_research"
    description = "Run the full multi-iteration research loop for a trading idea"
    parameters = {
        "idea": {"type": "string", "description": "Research hypothesis or trading idea"},
        "symbol": {"type": "string", "description": "Stock symbol"},
        "from_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
        "to_date": {"type": "string", "description": "End date YYYY-MM-DD"},
        "interval": {
            "type": "string",
            "description": "Bar interval: 1m, 5m, 15m, 1h, 1D (default: 1D)",
        },
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_research", "http://localhost:8087")
        resp = httpx.post(
            f"{url}/research/run",
            json={
                "idea": kwargs["idea"],
                "symbol": kwargs["symbol"],
                "from_date": kwargs["from_date"],
                "to_date": kwargs["to_date"],
                "interval": kwargs.get("interval", "1D"),
            },
            timeout=300,
        )
        resp.raise_for_status()
        return resp.text
