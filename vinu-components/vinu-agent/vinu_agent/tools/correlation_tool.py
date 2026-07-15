import json
from ..agent.tools import BaseTool


class CorrelationTool(BaseTool):
    name = "get_correlation"
    description = "Compute news-price correlation analysis for a symbol"
    parameters = {
        "symbol": {"type": "string", "description": "Stock symbol"},
        "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_correlation", "http://localhost:8083")
        resp = httpx.post(
            f"{url}/correlation/compute",
            json={
                "symbol": kwargs["symbol"],
                "start_date": kwargs["start_date"],
                "end_date": kwargs["end_date"],
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.text
