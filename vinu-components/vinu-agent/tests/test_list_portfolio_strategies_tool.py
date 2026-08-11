from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.list_portfolio_strategies_tool import ListPortfolioStrategiesTool


def _tool() -> ListPortfolioStrategiesTool:
    tool = ListPortfolioStrategiesTool()
    tool._services_config = {"vinu_portfolio": "http://vinu-portfolio:8090"}
    return tool


class TestListPortfolioStrategiesTool:
    def test_returns_active_strategies(self) -> None:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = [
            {"name": "ma_crossover", "kind": "yaml", "symbol": "AAPL", "weights_source": "vinu-strategy"},
            {"name": "llm_thesis_1", "kind": "llm_python", "symbol": "MSFT", "weights_source": "vinu-research"},
        ]
        with patch("httpx.get", return_value=resp):
            result = json.loads(_tool().execute())

        assert result["status"] == "ok"
        assert result["count"] == 2
        assert {"name": "ma_crossover", "kind": "yaml", "symbol": "AAPL", "weights_source": "vinu-strategy"} in result["strategies"]

    def test_uses_configured_service_url(self) -> None:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = []
        with patch("httpx.get", return_value=resp) as mock_get:
            _tool().execute()

        mock_get.assert_called_once_with("http://vinu-portfolio:8090/portfolio/strategies", timeout=10.0)

    def test_default_url_used_when_not_configured(self) -> None:
        tool = ListPortfolioStrategiesTool()  # _services_config left default {}
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = []
        with patch("httpx.get", return_value=resp) as mock_get:
            tool.execute()

        mock_get.assert_called_once_with("http://localhost:8090/portfolio/strategies", timeout=10.0)

    def test_unreachable_portfolio_fails_open_not_error(self) -> None:
        with patch("httpx.get", side_effect=ConnectionError("down")):
            result = json.loads(_tool().execute())

        assert result["status"] == "unavailable"
        assert result["strategies"] == []
