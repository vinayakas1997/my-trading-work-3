from unittest.mock import MagicMock, patch

from vinu_portfolio.circuit_breakers import PortfolioDrawdownMonitor
from vinu_portfolio.drawdown_scheduler import run_once


def _resp(json_body: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_body
    return resp


class TestRunOnce:
    def test_no_broker_account_configured(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        with patch(
            "vinu_portfolio.drawdown_scheduler.httpx.get",
            return_value=_resp({"configured": False, "equity": None}),
        ):
            result = run_once(monitor, "http://agent-api.test")

        assert result["status"] == "no_broker_account"

    def test_missing_equity_data(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        with patch(
            "vinu_portfolio.drawdown_scheduler.httpx.get",
            return_value=_resp({"configured": True, "equity": None}),
        ):
            result = run_once(monitor, "http://agent-api.test")

        assert result["status"] == "no_equity_data"

    def test_agent_api_unreachable(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        with patch(
            "vinu_portfolio.drawdown_scheduler.httpx.get",
            side_effect=ConnectionError("down"),
        ):
            result = run_once(monitor, "http://agent-api.test")

        assert result["status"] == "unavailable"

    def test_checked_updates_monitor(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        with patch(
            "vinu_portfolio.drawdown_scheduler.httpx.get",
            return_value=_resp({"configured": True, "equity": 100_000.0}),
        ):
            result = run_once(monitor, "http://agent-api.test")
        assert result["status"] == "checked"
        assert result["threshold_breached"] is False

        with patch(
            "vinu_portfolio.drawdown_scheduler.httpx.get",
            return_value=_resp({"configured": True, "equity": 75_000.0}),
        ), patch("vinu_portfolio.circuit_breakers.httpx.post", return_value=_resp({})) as mock_post:
            result = run_once(monitor, "http://agent-api.test")

        assert result["status"] == "checked"
        assert result["threshold_breached"] is True
        assert result["halted"] is True
        mock_post.assert_called_once()
