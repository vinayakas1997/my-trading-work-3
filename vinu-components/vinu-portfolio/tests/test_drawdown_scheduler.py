from unittest.mock import MagicMock, patch

from vinu_portfolio.circuit_breakers import PortfolioDrawdownMonitor
from vinu_portfolio.drawdown_scheduler import run_once
from vinu_portfolio.storage.drawdown_status import DrawdownStatusStore


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


class TestRunOnceWritesTheStore:
    """Item #23 findings #2/#3 fix: the real action this cycle computed
    must reach the same file compute_daily_allocation() reads, not just
    the in-memory result dict this function already returned."""

    def test_a_checked_cycle_writes_its_real_action(self, tmp_path) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        store = DrawdownStatusStore(str(tmp_path / "drawdown_status.db"))
        with patch(
            "vinu_portfolio.drawdown_scheduler.httpx.get",
            return_value=_resp({"configured": True, "equity": 100_000.0}),
        ):
            run_once(monitor, "http://agent-api.test", store=store)

        status = store.get()
        assert status.action == "ok"

    def test_an_unavailable_cycle_does_not_write_a_stale_ok(self, tmp_path) -> None:
        monitor = PortfolioDrawdownMonitor(unavailable_halt_threshold=3)
        store = DrawdownStatusStore(str(tmp_path / "drawdown_status.db"))
        store.record(action="ok", current_drawdown=0.0, threshold_breached=False)

        with patch("vinu_portfolio.drawdown_scheduler.httpx.get", side_effect=ConnectionError("down")):
            run_once(monitor, "http://agent-api.test", store=store)
            run_once(monitor, "http://agent-api.test", store=store)
            with patch("vinu_portfolio.circuit_breakers.httpx.post"):
                result = run_once(monitor, "http://agent-api.test", store=store)

        assert result["status"] == "unavailable"
        assert result["escalated_halt"] is True
        status = store.get()
        assert status.action == "halt"

    def test_store_is_optional_existing_callers_unaffected(self) -> None:
        monitor = PortfolioDrawdownMonitor(drawdown_threshold=-0.20)
        with patch(
            "vinu_portfolio.drawdown_scheduler.httpx.get",
            return_value=_resp({"configured": True, "equity": 100_000.0}),
        ):
            result = run_once(monitor, "http://agent-api.test")  # no store=

        assert result["status"] == "checked"
