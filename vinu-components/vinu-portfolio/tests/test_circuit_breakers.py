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
        assert args[0] == "http://agent-api.test:8086/agent/broker/halt"
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


class TestActionLadder:
    def test_ok_below_halve_threshold(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20, halve_threshold=-0.10, flat_threshold=-0.15)
        with patch("vinu_portfolio.circuit_breakers.httpx.post"):
            monitor.update(100_000.0)
            result = monitor.update(95_000.0)  # -5%
        assert result["action"] == "ok"

    def test_halve_between_halve_and_flat_thresholds(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20, halve_threshold=-0.10, flat_threshold=-0.15)
        with patch("vinu_portfolio.circuit_breakers.httpx.post"):
            monitor.update(100_000.0)
            result = monitor.update(88_000.0)  # -12%
        assert result["action"] == "halve"

    def test_flat_between_flat_and_halt_thresholds(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20, halve_threshold=-0.10, flat_threshold=-0.15)
        with patch("vinu_portfolio.circuit_breakers.httpx.post"):
            monitor.update(100_000.0)
            result = monitor.update(83_000.0)  # -17%
        assert result["action"] == "flat"

    def test_halt_at_drawdown_threshold(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20, halve_threshold=-0.10, flat_threshold=-0.15)
        with patch("vinu_portfolio.circuit_breakers.httpx.post"):
            monitor.update(100_000.0)
            result = monitor.update(75_000.0)  # -25%
        assert result["action"] == "halt"


class TestConsecutiveUnavailableEscalation:
    """Item #23 finding #4: an extended agent-api outage must eventually
    escalate to a real halt, not stay silently inert forever."""

    def test_below_threshold_does_not_escalate(self) -> None:
        monitor = PortfolioDrawdownMonitor(unavailable_halt_threshold=3)
        with patch("vinu_portfolio.circuit_breakers.httpx.post") as mock_post:
            r1 = monitor.note_unavailable()
            r2 = monitor.note_unavailable()

        assert r1["consecutive_unavailable"] == 1
        assert r2["consecutive_unavailable"] == 2
        assert r1["escalated_halt"] is False
        assert r2["escalated_halt"] is False
        mock_post.assert_not_called()

    def test_crossing_threshold_escalates_to_a_real_halt(self) -> None:
        monitor = PortfolioDrawdownMonitor(unavailable_halt_threshold=3, agent_api_url="http://agent-api.test")
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        with patch("vinu_portfolio.circuit_breakers.httpx.post", return_value=mock_resp) as mock_post:
            monitor.note_unavailable()
            monitor.note_unavailable()
            result = monitor.note_unavailable()

        assert result["consecutive_unavailable"] == 3
        assert result["escalated_halt"] is True
        assert result["action"] == "halt"
        mock_post.assert_called_once()
        assert mock_post.call_args.args[0] == "http://agent-api.test/agent/broker/halt"

    def test_a_successful_update_resets_the_streak(self) -> None:
        monitor = PortfolioDrawdownMonitor(unavailable_halt_threshold=3)
        with patch("vinu_portfolio.circuit_breakers.httpx.post") as mock_post:
            monitor.note_unavailable()
            monitor.note_unavailable()
            monitor.update(100_000.0)  # agent-api reachable again
            r3 = monitor.note_unavailable()

        assert r3["consecutive_unavailable"] == 1  # streak restarted, not 3
        assert r3["escalated_halt"] is False
        mock_post.assert_not_called()

    def test_env_var_default_used_when_not_passed(self) -> None:
        with patch.dict("os.environ", {"VINU_AGENT_API_URL": "http://from-env:9999"}):
            monitor = PortfolioDrawdownMonitor()
        assert monitor._agent_api_url == "http://from-env:9999"


class TestAbsoluteLossBreaker:
    """Stage A (A16): a second breaker on absolute loss from the session's
    STARTING equity, independent of drawdown-from-peak. Disabled unless a
    non-zero threshold is set."""

    def test_disabled_by_default(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        with patch("vinu_portfolio.circuit_breakers.httpx.post") as mock_post:
            monitor.update(100_000.0)
            # -18% from start but drawdown-from-peak is also -18%, under -20%
            result = monitor.update(82_000.0)
        assert result["halted"] is False
        assert result["abs_loss_breached"] is False
        mock_post.assert_not_called()

    def test_trips_on_loss_from_start_before_drawdown_would(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        monitor = PortfolioDrawdownMonitor(
            drawdown_threshold=-0.20, abs_loss_threshold=-0.10,
            agent_api_url="http://agent-api.test:8086",
        )
        with patch("vinu_portfolio.circuit_breakers.httpx.post", return_value=mock_resp) as mock_post:
            monitor.update(100_000.0)          # start = peak = 100k
            monitor.update(101_000.0)          # tiny new high; peak now 101k
            result = monitor.update(89_000.0)  # -11.9% vs peak (under -20%), -11% vs start
        assert result["abs_loss_breached"] is True
        assert result["halted"] is True
        assert result["action"] == "halt"
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert "starting equity" in kwargs["json"]["reason"]

    def test_negative_or_positive_threshold_sign_is_normalised(self) -> None:
        # passing 0.10 (positive) is treated the same as -0.10
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20, abs_loss_threshold=0.10)
        with patch("vinu_portfolio.circuit_breakers.httpx.post") as mock_post:
            monitor.update(100_000.0)
            result = monitor.update(85_000.0)
        assert result["abs_loss_breached"] is True
        mock_post.assert_called_once()

    def test_reset_clears_start_value(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20, abs_loss_threshold=-0.10)
        monitor.update(100_000.0)
        monitor.reset()
        with patch("vinu_portfolio.circuit_breakers.httpx.post") as mock_post:
            # new session starts at 80k; 76k is -5% from the new start, no trip
            monitor.update(80_000.0)
            result = monitor.update(76_000.0)
        assert result["abs_loss_breached"] is False
        mock_post.assert_not_called()

    def test_env_var_configures_threshold(self) -> None:
        with patch.dict("os.environ", {"VINU_PORTFOLIO_ABS_LOSS_HALT": "-0.12"}):
            monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        assert monitor._abs_loss_threshold == -0.12
