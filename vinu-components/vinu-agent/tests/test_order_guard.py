from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.broker.alpaca import Account
from vinu_agent.broker.mandate import TradingMandate
from vinu_agent.broker.order_guard import OrderGuard


def _account(equity: float = 100_000.0, cash: float = 100_000.0) -> Account:
    return Account(
        account_id="test",
        status="ACTIVE",
        currency="USD",
        cash=cash,
        portfolio_value=equity,
        buying_power=cash,
        equity=equity,
        daytrade_count=0,
        pattern_day_trader=False,
    )


def _guard(mandate: TradingMandate) -> OrderGuard:
    broker = MagicMock()
    broker.get_account.return_value = _account()
    return OrderGuard(mandate=mandate, broker=broker)


class TestRequireActiveArtifact:
    def test_rejects_when_no_active_artifact_for_symbol(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0)
        guard = _guard(mandate)

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = [{"artifact_id": "a1", "universe": ["MSFT"], "status": "ACTIVE"}]

        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert not result
        assert "ACTIVE strategy artifact" in result.reason

    def test_allows_when_active_artifact_covers_symbol(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0)
        guard = _guard(mandate)

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = [{"artifact_id": "a1", "universe": ["AAPL"], "status": "ACTIVE"}]

        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert result

    def test_disabled_via_mandate_skips_check(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        guard = _guard(mandate)

        with patch("vinu_agent.broker.order_guard.requests.get") as mock_get:
            result = guard.check("AAPL", "buy", qty=10, price=100.0)

        mock_get.assert_not_called()
        assert result

    def test_fails_open_when_research_api_unreachable(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0)
        guard = _guard(mandate)

        with patch("vinu_agent.broker.order_guard.requests.get", side_effect=ConnectionError("down")):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert result


class TestRequireMarketOpen:
    def test_rejects_when_market_closed(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        broker.get_clock.return_value = {"is_open": False, "next_open": "2026-07-21T13:30:00Z"}
        guard = OrderGuard(mandate=mandate, broker=broker)

        result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert not result
        assert "Market is closed" in result.reason

    def test_allows_when_market_open(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        broker.get_clock.return_value = {"is_open": True}
        guard = OrderGuard(mandate=mandate, broker=broker)

        result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert result

    def test_disabled_via_mandate_skips_clock_call(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, require_market_open=False)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        guard = OrderGuard(mandate=mandate, broker=broker)

        result = guard.check("AAPL", "buy", qty=10, price=100.0)

        broker.get_clock.assert_not_called()
        assert result

    def test_fails_open_when_clock_call_errors(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        broker.get_clock.side_effect = ConnectionError("down")
        guard = OrderGuard(mandate=mandate, broker=broker)

        result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert result


class TestPortfolioConcentration:
    def test_sell_orders_are_never_blocked(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_symbol_concentration_pct=0.1, allow_short=True,
        )
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.requests.get") as mock_get:
            result = guard.check("AAPL", "sell", qty=10, price=100.0)
        mock_get.assert_not_called()
        assert result

    def test_rejects_when_symbol_already_over_concentration_cap(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_symbol_concentration_pct=0.2,
        )
        guard = _guard(mandate)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "weights": [{"name": "s1", "symbol": "AAPL", "target_weight": 0.35}],
            "correlation_matrix": None,
        }
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        assert not result
        assert "max_symbol_concentration_pct" in result.reason

    def test_allows_when_within_concentration_cap(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_symbol_concentration_pct=0.5,
        )
        guard = _guard(mandate)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "weights": [{"name": "s1", "symbol": "AAPL", "target_weight": 0.2}],
            "correlation_matrix": None,
        }
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        assert result

    def test_rejects_on_high_correlation_with_held_symbol(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_pairwise_correlation=0.8,
        )
        guard = _guard(mandate)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "weights": [
                {"name": "s_msft", "symbol": "MSFT", "target_weight": 0.3},
                {"name": "s_aapl", "symbol": "AAPL", "target_weight": 0.0},
            ],
            "correlation_matrix": {
                "strategies": ["s_aapl", "s_msft"],
                "values": [[1.0, 0.92], [0.92, 1.0]],
            },
        }
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        assert not result
        assert "max_pairwise_correlation" in result.reason

    def test_allows_when_correlation_below_threshold(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_pairwise_correlation=0.8,
        )
        guard = _guard(mandate)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "weights": [
                {"name": "s_msft", "symbol": "MSFT", "target_weight": 0.3},
                {"name": "s_aapl", "symbol": "AAPL", "target_weight": 0.0},
            ],
            "correlation_matrix": {
                "strategies": ["s_aapl", "s_msft"],
                "values": [[1.0, 0.3], [0.3, 1.0]],
            },
        }
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        assert result

    def test_fails_open_when_portfolio_api_unreachable(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_symbol_concentration_pct=0.2,
        )
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.requests.get", side_effect=ConnectionError("down")):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        assert result

    def test_disabled_by_default_skips_call(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, require_market_open=False)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.requests.get") as mock_get:
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        mock_get.assert_not_called()
        assert result


class TestMaxCapitalUtilization:
    def test_rejects_when_projected_utilization_exceeds_cap(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, max_capital_utilization_pct=0.6, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account(equity=100_000.0, cash=50_000.0)
        guard = OrderGuard(mandate=mandate, broker=broker)

        result = guard.check("AAPL", "buy", qty=200, price=100.0)

        assert not result
        assert "max_capital_utilization_pct" in result.reason

    def test_allows_when_within_cap(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, max_capital_utilization_pct=0.6, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account(equity=100_000.0, cash=90_000.0)
        guard = OrderGuard(mandate=mandate, broker=broker)

        result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert result
