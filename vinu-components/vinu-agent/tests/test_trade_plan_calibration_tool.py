import json
from unittest.mock import patch

from vinu_agent.tools.trade_plan_calibration_tool import GetTradePlanCalibrationTool


def _tool(services_config: dict | None = None) -> GetTradePlanCalibrationTool:
    tool = GetTradePlanCalibrationTool()
    tool._services_config = services_config or {}
    return tool


class TestGetTradePlanCalibrationTool:
    def test_returns_real_calibration_result(self) -> None:
        with patch(
            "vinu_agent.agent.trade_plan_calibration.get_trade_plan_calibration",
            return_value={"artifact_id": "art_1", "n_entries": 12, "passed": True, "reasons": [], "source": "in_process"},
        ) as mock_get:
            result = json.loads(_tool().execute(artifact_id="art_1"))

        assert result["passed"] is True
        assert result["n_entries"] == 12
        mock_get.assert_called_once()

    def test_uses_configured_research_api_url(self) -> None:
        with patch(
            "vinu_agent.agent.trade_plan_calibration.get_trade_plan_calibration",
            return_value={"artifact_id": "art_1", "n_entries": 0, "passed": False, "reasons": [], "source": "error"},
        ) as mock_get:
            _tool({"vinu_research": "http://research-api:8087"}).execute(artifact_id="art_1")

        _, kwargs = mock_get.call_args
        assert kwargs["research_api_url"] == "http://research-api:8087"
