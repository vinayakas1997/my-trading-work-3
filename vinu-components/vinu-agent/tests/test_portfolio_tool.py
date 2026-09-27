"""portfolio_tool.py had zero test coverage before this file, despite
feeding live positions/orders into sizing and risk decisions elsewhere in
the agent. A real, previously-untested risk found while writing these:
with section="all", a single broker call failing partway through used to
discard every section already fetched -- the whole response collapsed
into a bare error, losing account data that genuinely did come back.
Fixed alongside these tests (each section is now independently
try/excepted; a partial success still returns what it has, with a
per-section error recorded, only becoming status="error" when every
requested section failed)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.portfolio_tool import PortfolioTool


def _account(**overrides) -> MagicMock:
    a = MagicMock()
    a.status = overrides.get("status", "ACTIVE")
    a.currency = overrides.get("currency", "USD")
    a.cash = overrides.get("cash", 10_000.0)
    a.portfolio_value = overrides.get("portfolio_value", 50_000.0)
    a.buying_power = overrides.get("buying_power", 20_000.0)
    a.equity = overrides.get("equity", 50_000.0)
    a.daytrade_count = overrides.get("daytrade_count", 0)
    a.pattern_day_trader = overrides.get("pattern_day_trader", False)
    return a


def _position(**overrides) -> MagicMock:
    p = MagicMock()
    p.symbol = overrides.get("symbol", "AAPL")
    p.qty = overrides.get("qty", 10.0)
    p.market_value = overrides.get("market_value", 1_500.0)
    p.cost_basis = overrides.get("cost_basis", 1_400.0)
    p.unrealized_pl = overrides.get("unrealized_pl", 100.0)
    p.unrealized_plpc = overrides.get("unrealized_plpc", 0.0714)
    p.current_price = overrides.get("current_price", 150.0)
    p.avg_entry_price = overrides.get("avg_entry_price", 140.0)
    return p


def _order(**overrides) -> MagicMock:
    o = MagicMock()
    o.order_id = overrides.get("order_id", "o1")
    o.symbol = overrides.get("symbol", "AAPL")
    o.side = overrides.get("side", "buy")
    o.type = overrides.get("type", "market")
    o.status = overrides.get("status", "open")
    o.qty = overrides.get("qty", 5.0)
    o.filled_qty = overrides.get("filled_qty", 0.0)
    o.limit_price = overrides.get("limit_price", None)
    o.stop_price = overrides.get("stop_price", None)
    o.created_at = overrides.get("created_at", "2024-01-01T00:00:00Z")
    return o


def _configured_broker() -> MagicMock:
    broker = MagicMock()
    broker.is_configured.return_value = True
    broker.get_account.return_value = _account()
    broker.get_positions.return_value = [_position()]
    broker.get_orders.return_value = [_order()]
    return broker


class TestPortfolioToolSections:
    def test_not_configured_returns_error_without_calling_broker_methods(self) -> None:
        broker = MagicMock()
        broker.is_configured.return_value = False
        with patch("vinu_agent.tools.portfolio_tool.get_live_broker", return_value=broker):
            result = json.loads(PortfolioTool().execute())
        assert result["status"] == "error"
        broker.get_account.assert_not_called()

    def test_all_section_returns_account_positions_and_orders(self) -> None:
        broker = _configured_broker()
        with patch("vinu_agent.tools.portfolio_tool.get_live_broker", return_value=broker):
            result = json.loads(PortfolioTool().execute())
        assert result["status"] == "ok"
        assert result["account"]["cash"] == 10_000.0
        assert result["positions"][0]["symbol"] == "AAPL"
        assert result["positions_summary"]["count"] == 1
        assert result["orders"][0]["order_id"] == "o1"

    def test_account_only_section_does_not_fetch_positions_or_orders(self) -> None:
        broker = _configured_broker()
        with patch("vinu_agent.tools.portfolio_tool.get_live_broker", return_value=broker):
            result = json.loads(PortfolioTool().execute(section="account"))
        assert "account" in result
        assert "positions" not in result
        assert "orders" not in result
        broker.get_positions.assert_not_called()
        broker.get_orders.assert_not_called()

    def test_positions_only_section(self) -> None:
        broker = _configured_broker()
        with patch("vinu_agent.tools.portfolio_tool.get_live_broker", return_value=broker):
            result = json.loads(PortfolioTool().execute(section="positions"))
        assert "positions" in result
        assert "account" not in result
        assert "orders" not in result

    def test_orders_only_section(self) -> None:
        broker = _configured_broker()
        with patch("vinu_agent.tools.portfolio_tool.get_live_broker", return_value=broker):
            result = json.loads(PortfolioTool().execute(section="orders"))
        assert "orders" in result
        assert "account" not in result
        assert "positions" not in result

    def test_positions_summary_sums_market_value_and_pl_across_positions(self) -> None:
        broker = _configured_broker()
        broker.get_positions.return_value = [
            _position(symbol="AAPL", market_value=1000.0, unrealized_pl=50.0),
            _position(symbol="MSFT", market_value=2000.0, unrealized_pl=-25.0),
        ]
        with patch("vinu_agent.tools.portfolio_tool.get_live_broker", return_value=broker):
            result = json.loads(PortfolioTool().execute(section="positions"))
        assert result["positions_summary"]["count"] == 2
        assert result["positions_summary"]["total_market_value"] == 3000.0
        assert result["positions_summary"]["total_unrealized_pl"] == 25.0


class TestPortfolioToolPartialFailure:
    """Regression for the discard-everything-on-any-failure bug found
    while writing this file: previously, positions failing after account
    already succeeded lost the account data too."""

    def test_one_section_failing_still_returns_the_sections_that_succeeded(self) -> None:
        broker = _configured_broker()
        broker.get_positions.side_effect = RuntimeError("alpaca 500")
        with patch("vinu_agent.tools.portfolio_tool.get_live_broker", return_value=broker):
            result = json.loads(PortfolioTool().execute())
        assert result["status"] == "ok"  # partial success, not a total failure
        assert result["account"]["cash"] == 10_000.0
        assert "positions" not in result
        assert result["orders"][0]["order_id"] == "o1"
        assert result["errors"]["positions"] == "alpaca 500"

    def test_every_requested_section_failing_is_a_real_error_status(self) -> None:
        broker = _configured_broker()
        broker.get_account.side_effect = RuntimeError("boom")
        with patch("vinu_agent.tools.portfolio_tool.get_live_broker", return_value=broker):
            result = json.loads(PortfolioTool().execute(section="account"))
        assert result["status"] == "error"
        assert result["errors"]["account"] == "boom"


class TestPortfolioToolHistoricalReplay:
    def test_as_of_set_uses_the_historical_broker_not_the_live_one(self) -> None:
        tool = PortfolioTool()
        tool._as_of = "2024-06-01T00:00:00Z"
        tool._session_id = "sess-1"
        historical = _configured_broker()
        with patch("vinu_agent.tools.portfolio_tool.HistoricalFillBroker", return_value=historical) as MockHist, \
             patch("vinu_agent.tools.portfolio_tool.get_live_broker") as mock_live:
            result = json.loads(tool.execute())
        MockHist.assert_called_once_with(
            as_of="2024-06-01T00:00:00Z", state_path="/data/replay_state/sess-1.json",
        )
        mock_live.assert_not_called()
        assert result["status"] == "ok"

    def test_no_as_of_uses_the_live_broker(self) -> None:
        broker = _configured_broker()
        with patch("vinu_agent.tools.portfolio_tool.get_live_broker", return_value=broker) as mock_live, \
             patch("vinu_agent.tools.portfolio_tool.HistoricalFillBroker") as MockHist:
            PortfolioTool().execute()
        mock_live.assert_called_once()
        MockHist.assert_not_called()
