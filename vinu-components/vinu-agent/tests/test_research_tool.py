import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_agent.tools.research_tool import ResearchTool


def _tool(services_config: dict | None = None) -> ResearchTool:
    tool = ResearchTool()
    tool._services_config = services_config or {}
    return tool


def _force_in_process_unavailable():
    """item #17 finding #3: research_link.py's own module docstring
    documents ImportError specifically as the one legitimate reason the
    in-process path falls back to HTTP (vinu-research not installed in
    this deployment) -- so that's what these tests simulate, not a
    generic RuntimeError standing in for "anything went wrong"."""
    return patch(
        "vinu_agent.broker.research_link.get_research_service",
        side_effect=ImportError("vinu_research not installed"),
    )


def _mock_research_service(result: dict) -> MagicMock:
    """A fake ResearchService -- the real one runs the actual multi-
    iteration LLM+backtest loop, far too heavy for a unit test. This
    confirms ResearchTool wires kwargs through to run_research() and
    passes its dict result back unchanged, not that the loop itself
    works (covered by vinu-research's own test suite)."""
    service = MagicMock()
    service.run_research = AsyncMock(return_value=result)
    service.close = AsyncMock()
    return service


class TestResearchToolInProcess:
    def test_sends_user_idea_kwarg_not_idea(self) -> None:
        service = _mock_research_service({"status": "done"})
        with patch("vinu_agent.broker.research_link.get_research_service", return_value=service):
            result = json.loads(_tool().execute(
                idea="trend-following on AAPL", symbol="AAPL",
                from_date="2024-01-01", to_date="2024-12-31",
            ))
        assert result == {"status": "done"}
        _, kwargs = service.run_research.call_args
        assert kwargs["user_idea"] == "trend-following on AAPL"
        assert kwargs["symbol"] == "AAPL"
        assert kwargs["from_date"] == "2024-01-01"
        assert kwargs["to_date"] == "2024-12-31"

    def test_optional_fields_parsed_and_passed_through(self) -> None:
        service = _mock_research_service({})
        with patch("vinu_agent.broker.research_link.get_research_service", return_value=service):
            _tool().execute(
                idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31",
                indicators="sma_20, rsi_14", initial_capital=50000, universe="MSFT, GOOGL", dry_run=True,
            )
        _, kwargs = service.run_research.call_args
        assert kwargs["indicators"] == ["sma_20", "rsi_14"]
        assert kwargs["initial_capital"] == 50000
        assert kwargs["universe"] == ["MSFT", "GOOGL"]
        assert kwargs["dry_run"] is True
        service.close.assert_awaited_once()

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        mock_resp = MagicMock()
        mock_resp.text = '{"status": "done"}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            result = _tool().execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
        assert result == '{"status": "done"}'
        mock_post.assert_called_once()

    def test_a_real_infrastructure_error_propagates_instead_of_retrying_over_http(self) -> None:
        """item #17 finding #3, the actual fix: a real InfrastructureError
        (or any other genuine failure) raised *inside* the research loop
        must NOT be caught by the same except clause that triggers the
        HTTP fallback -- that used to silently stack a second, duplicate,
        expensive multi-iteration run over HTTP on top of the one that
        already ran and genuinely failed. It must propagate instead, so
        ToolRegistry.execute()'s own except Exception (tools.py) can turn
        it into a real error response rather than this masking it."""
        from vinu_research.tools import InfrastructureError

        service = MagicMock()
        service.run_research = AsyncMock(
            side_effect=InfrastructureError("simulator down, do not retry")
        )
        service.close = AsyncMock()
        with patch("vinu_agent.broker.research_link.get_research_service", return_value=service), \
                patch("httpx.post") as mock_post:
            with pytest.raises(InfrastructureError):
                _tool().execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
        mock_post.assert_not_called()

    def test_a_generic_bug_in_the_loop_also_propagates_instead_of_retrying(self) -> None:
        service = MagicMock()
        service.run_research = AsyncMock(side_effect=ValueError("real bug"))
        service.close = AsyncMock()
        with patch("vinu_agent.broker.research_link.get_research_service", return_value=service), \
                patch("httpx.post") as mock_post:
            with pytest.raises(ValueError):
                _tool().execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
        mock_post.assert_not_called()


class TestResearchToolHttpFallback:
    def test_sends_user_idea_not_idea(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = '{"status": "done"}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
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
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
        args, _ = mock_post.call_args
        assert args[0] == "http://research-api:8087/research/run"

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:8087/research/run"

    def test_optional_fields_passed_through(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
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
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
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
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp):
            try:
                tool.execute(idea="idea", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31")
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
