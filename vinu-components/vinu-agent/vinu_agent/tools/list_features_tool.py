import json

from ..agent.tools import BaseTool


class ListAvailableFeaturesTool(BaseTool):
    name = "list_available_features"
    description = (
        "List every real indicator and preset vinu-tools can actually compute, from the "
        "live catalog -- not a fixed/example list. Call this BEFORE get_features so you know "
        "what's really available (there are more than SMA/RSI/MACD -- e.g. supertrend, cmf, "
        "aroon, session, and preset bundles like alpha101_benchmark) instead of guessing "
        "indicator names from general knowledge."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_tools", "http://localhost:8082")
        with httpx.Client(timeout=30.0) as client:
            catalog_resp = client.get(f"{url}/features/catalog")
            catalog_resp.raise_for_status()
            presets_resp = client.get(f"{url}/features/presets")
            presets_resp.raise_for_status()

        indicators = [
            {"kind": f["kind"], "description": f["description"], "examples": f.get("examples", [])}
            for f in catalog_resp.json().get("data", [])
        ]
        # Preset feature lists aren't expanded here -- alpha101/alpha158/alpha360
        # alone are 101-360 entries each; a caller who wants one just passes
        # its name as get_features' `preset` param, the service expands it.
        presets = [
            {"name": p["name"], "description": p.get("description", ""), "feature_count": len(p.get("features", []))}
            for p in presets_resp.json().get("data", [])
        ]
        return json.dumps({"indicators": indicators, "presets": presets})
