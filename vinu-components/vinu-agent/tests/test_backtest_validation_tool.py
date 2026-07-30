import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.backtest_validation_tool import BacktestValidationTool


def _tool(services_config: dict | None = None) -> BacktestValidationTool:
    tool = BacktestValidationTool()
    tool._services_config = services_config or {}
    return tool


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


class TestBacktestValidationTool:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _tool({"vinu_simulator": "http://simulator-api:8085"})
        mock_resp = _mock_response({
            "metrics": {"sharpe_ratio": 1.2},
            "benchmark_metrics": {},
            "trades": [{"id": 1}, {"id": 2}],
            "validation": {"all_passed": True, "reasons": []},
        })
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute(run_id="abc123")
        args, _ = mock_get.call_args
        assert args[0] == "http://simulator-api:8085/simulator/results/abc123"
        data = json.loads(result)
        assert data["run_id"] == "abc123"
        assert data["metrics"] == {"sharpe_ratio": 1.2}
        assert data["validation"] == {"all_passed": True, "reasons": []}
        assert data["trade_count"] == 2
        assert "trades" not in data

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = _mock_response({"metrics": {}, "validation": None})
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(run_id="xyz")
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8085/simulator/results/xyz"

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with patch("httpx.get", return_value=mock_resp):
            try:
                tool.execute(run_id="abc")
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
