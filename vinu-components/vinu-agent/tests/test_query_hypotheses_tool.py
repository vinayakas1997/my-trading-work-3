from unittest.mock import MagicMock, patch

from vinu_agent.tools.query_hypotheses_tool import QueryHypothesesTool


def _tool(services_config: dict | None = None) -> QueryHypothesesTool:
    tool = QueryHypothesesTool()
    tool._services_config = services_config or {}
    return tool


class TestQueryHypothesesTool:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"count": 0, "hypotheses": []}'
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute()
        args, kwargs = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/hypotheses"
        assert kwargs["params"] == {}
        assert result == '{"count": 0, "hypotheses": []}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute()
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/hypotheses"

    def test_passes_symbol_and_status_filters(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(symbol="AAPL", status="validated")
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"symbol": "AAPL", "status": "validated"}

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with patch("httpx.get", return_value=mock_resp):
            try:
                tool.execute()
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
