import json
from typing import Any

from ..agent.tools import BaseTool


class GetTradePlanCalibrationTool(BaseTool):
    name = "get_trade_plan_calibration"
    description = (
        "Read a trade-plan artifact's real historical forecast calibration (Phase 8) -- how "
        "often its forecasts have actually been right, over how many observations. Works "
        "regardless of whether vinu-research is reached in-process or over HTTP. Only "
        "meaningful for an artifact_id of type='trade_plan' (see get_all_angles/query_hypotheses "
        "for how to find one for this ticker, if any exists) -- this is NOT a per-angle trust "
        "signal, no per-angle historical calibration tracker exists in this system."
    )
    parameters = {
        "type": "object",
        "properties": {
            "artifact_id": {"type": "string", "description": "A type='trade_plan' artifact id"},
        },
        "required": ["artifact_id"],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs: Any) -> str:
        from ..agent.trade_plan_calibration import get_trade_plan_calibration

        research_api_url = self._services_config.get("vinu_research", "http://localhost:8087")
        result = get_trade_plan_calibration(kwargs["artifact_id"], research_api_url=research_api_url)
        return json.dumps(result)
