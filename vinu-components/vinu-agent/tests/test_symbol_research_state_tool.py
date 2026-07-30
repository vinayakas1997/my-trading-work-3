from unittest.mock import MagicMock, patch

from vinu_agent.tools.symbol_research_state_tool import SymbolResearchStateTool


def _tool(services_config: dict | None = None) -> SymbolResearchStateTool:
    tool = SymbolResearchStateTool()
    tool._services_config = services_config or {}
    return tool


class TestSymbolResearchStateTool:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"symbol": "AAPL", "exhausted": false, "catalog_entry": null}'
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute(symbol="AAPL")
        args, _ = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/symbols/AAPL/state"
        assert result == '{"symbol": "AAPL", "exhausted": false, "catalog_entry": null}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(symbol="MSFT")
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/symbols/MSFT/state"

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with patch("httpx.get", return_value=mock_resp):
            try:
                tool.execute(symbol="AAPL")
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
