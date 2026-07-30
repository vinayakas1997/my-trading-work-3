from unittest.mock import MagicMock, patch

from vinu_agent.tools.run_checkpoints_tool import RunCheckpointsTool


def _tool(services_config: dict | None = None) -> RunCheckpointsTool:
    tool = RunCheckpointsTool()
    tool._services_config = services_config or {}
    return tool


class TestRunCheckpointsTool:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"run_id": 5, "count": 0, "checkpoints": []}'
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute(run_id=5)
        args, kwargs = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/runs/5/checkpoints"
        assert kwargs["params"] == {}
        assert result == '{"run_id": 5, "count": 0, "checkpoints": []}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(run_id=1)
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/runs/1/checkpoints"

    def test_passes_latest_only(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(run_id=1, latest_only=True)
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"latest_only": True}

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with patch("httpx.get", return_value=mock_resp):
            try:
                tool.execute(run_id=1)
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
