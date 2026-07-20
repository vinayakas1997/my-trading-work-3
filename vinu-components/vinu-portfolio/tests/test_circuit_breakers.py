from unittest.mock import MagicMock, patch

from vinu_portfolio.circuit_breakers import PortfolioDrawdownMonitor


class TestPortfolioDrawdownMonitor:
    def test_no_halt_within_threshold(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        with patch("vinu_portfolio.circuit_breakers.httpx.post") as mock_post:
            result = monitor.update(100_000.0)
            result = monitor.update(90_000.0)

        assert result["threshold_breached"] is False
        assert result["halted"] is False
        mock_post.assert_not_called()

    def test_halt_triggers_http_call_to_agent_api(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20, agent_api_url="http://agent-api.test:8086")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch("vinu_portfolio.circuit_breakers.httpx.post", return_value=mock_resp) as mock_post:
            monitor.update(100_000.0)
            result = monitor.update(75_000.0)

        assert result["threshold_breached"] is True
        assert result["halted"] is True
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://agent-api.test:8086/broker/halt"
        assert "reason" in kwargs["json"]

    def test_failed_halt_call_does_not_raise(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        with patch("vinu_portfolio.circuit_breakers.httpx.post", side_effect=ConnectionError("down")):
            monitor.update(100_000.0)
            result = monitor.update(75_000.0)

        assert result["halted"] is True

    def test_reset_clears_peak(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        monitor.update(100_000.0)
        monitor.reset()
        with patch("vinu_portfolio.circuit_breakers.httpx.post") as mock_post:
            result = monitor.update(50_000.0)

        assert result["threshold_breached"] is False
        mock_post.assert_not_called()

    def test_env_var_default_used_when_not_passed(self) -> None:
        with patch.dict("os.environ", {"VINU_AGENT_API_URL": "http://from-env:9999"}):
            monitor = PortfolioDrawdownMonitor()
        assert monitor._agent_api_url == "http://from-env:9999"
