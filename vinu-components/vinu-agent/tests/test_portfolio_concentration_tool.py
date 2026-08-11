"""Tests for GetPortfolioConcentrationTool -- real vinu-portfolio
concentration context for risk_gatekeeper's exposure_reviewer. See
vinu_agent/tools/portfolio_concentration_tool.py's module docstring.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.portfolio_concentration_tool import GetPortfolioConcentrationTool


def _tool() -> GetPortfolioConcentrationTool:
    tool = GetPortfolioConcentrationTool()
    tool._services_config = {"vinu_portfolio": "http://vinu-portfolio:8090"}
    return tool


class TestGetPortfolioConcentrationTool:
    def test_missing_symbol_is_an_error(self) -> None:
        result = json.loads(_tool().execute())
        assert result["status"] == "error"

    def test_returns_existing_target_weight_for_symbol(self) -> None:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "weights": [
                {"symbol": "AAPL", "target_weight": 0.15},
                {"symbol": "MSFT", "target_weight": 0.10},
            ],
        }
        with patch("httpx.get", return_value=resp) as mock_get:
            result = json.loads(_tool().execute(symbol="aapl"))

        assert result["status"] == "ok"
        assert result["symbol"] == "AAPL"
        assert result["existing_target_weight"] == 0.15
        assert {"symbol": "MSFT", "target_weight": 0.10} in result["all_weights"]
        mock_get.assert_called_once_with("http://vinu-portfolio:8090/portfolio/state", timeout=10.0)

    def test_symbol_not_currently_targeted_is_zero(self) -> None:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"weights": [{"symbol": "MSFT", "target_weight": 0.10}]}
        with patch("httpx.get", return_value=resp):
            result = json.loads(_tool().execute(symbol="AAPL"))

        assert result["existing_target_weight"] == 0.0

    def test_multiple_entries_for_same_symbol_summed(self) -> None:
        """Mirrors order_guard.py's own _check_portfolio_concentration
        summation -- more than one strategy targeting the same symbol
        should combine into one real exposure figure."""
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "weights": [
                {"symbol": "AAPL", "target_weight": 0.10},
                {"symbol": "AAPL", "target_weight": 0.05},
            ],
        }
        with patch("httpx.get", return_value=resp):
            result = json.loads(_tool().execute(symbol="AAPL"))

        assert result["existing_target_weight"] == pytest.approx(0.15)

    def test_unreachable_portfolio_fails_open_not_error(self) -> None:
        with patch("httpx.get", side_effect=ConnectionError("down")):
            result = json.loads(_tool().execute(symbol="AAPL"))

        assert result["status"] == "unavailable"
        assert result["symbol"] == "AAPL"

    def test_default_url_used_when_not_configured(self) -> None:
        tool = GetPortfolioConcentrationTool()  # _services_config left default {}
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"weights": []}
        with patch("httpx.get", return_value=resp) as mock_get:
            tool.execute(symbol="AAPL")

        mock_get.assert_called_once_with("http://localhost:8090/portfolio/state", timeout=10.0)
