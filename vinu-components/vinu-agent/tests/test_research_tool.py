from unittest.mock import MagicMock, patch

from vinu_agent.tools.research_tool import ResearchTool


def _tool(services_config: dict | None = None) -> ResearchTool:
    tool = ResearchTool()
    tool._services_config = services_config or {}
    return tool


class TestResearchTool:
    def test_sends_user_idea_not_idea(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = '{"status": "done"}'
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = tool.execute(
                idea="trend-following on AAPL",
                symbol="AAPL",
                from_date="2024-01-01",
                to_date="2024-12-31",
            )
        assert result == '{"status": "done"}'
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["user_idea"] == "trend-following on AAPL"
        assert "idea" not in payload
        assert "interval" not in payload
        assert payload["symbol"] == "AAPL"
        assert payload["from_date"] == "2024-01-01"
        assert payload["to_date"] == "2024-12-31"

    def test_uses_configured_service_url(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
        args, _ = mock_post.call_args
        assert args[0] == "http://research-api:8087/research/run"

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:8087/research/run"

    def test_optional_fields_passed_through(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(
                idea="idea",
                symbol="AAPL",
                from_date="2024-01-01",
                to_date="2024-12-31",
                indicators="sma_20, rsi_14",
                initial_capital=50000,
                universe="MSFT, GOOGL",
                dry_run=True,
            )
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["indicators"] == ["sma_20", "rsi_14"]
        assert payload["initial_capital"] == 50000
        assert payload["universe"] == ["MSFT", "GOOGL"]
        assert payload["dry_run"] is True

    def test_optional_fields_omitted_when_not_given(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert "indicators" not in payload
        assert "initial_capital" not in payload
        assert "universe" not in payload
        assert "dry_run" not in payload

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with patch("httpx.post", return_value=mock_resp):
            try:
                tool.execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
