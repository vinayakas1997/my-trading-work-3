from ..agent.tools import BaseTool


class GetAllAnglesTool(BaseTool):
    name = "get_all_angles"
    description = (
        "Fetch every vinu-initial-analysis angle's latest computed result for one ticker, "
        "in a single call. Angles with no data yet are reported as such (row_count=0), "
        "not omitted -- always check row_count before treating an angle as informative."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Stock symbol, e.g. AAPL"},
        },
        "required": ["ticker"],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import json
        import httpx

        ticker = kwargs["ticker"].strip().upper()
        base = self._services_config.get("vinu_initial_analysis", "http://localhost:8083").rstrip("/")
        url = f"{base}/analysis"

        with httpx.Client(timeout=30.0) as client:
            angles_resp = client.get(f"{url}/angles")
            angles_resp.raise_for_status()
            # /analysis/angles returns a list of metadata objects
            # ({name, title, purpose, path, spec}), not flat name strings.
            angle_names = [a["name"] for a in angles_resp.json().get("angles", [])]

            results = {}
            for name in angle_names:
                try:
                    resp = client.get(f"{url}/angle/{name}/{ticker}")
                    resp.raise_for_status()
                    results[name] = resp.json()
                except Exception as exc:
                    results[name] = {"symbol": ticker, "angle": name, "error": str(exc), "row_count": 0, "data": []}

        with_data = sum(1 for r in results.values() if r.get("row_count", 0) > 0)
        return json.dumps({
            "ticker": ticker,
            "angle_count": len(angle_names),
            "angles_with_data": with_data,
            "angles": results,
        })
