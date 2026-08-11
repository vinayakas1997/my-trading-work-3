import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.broker.alpaca import Account
from vinu_agent.broker.daily_limits import DailyLimitStore
from vinu_agent.broker.mandate import TradingMandate
from vinu_agent.broker.order_guard import OrderGuard
from vinu_research.models import Artifact, ArtifactStatus
from vinu_research.storage.strategy_store import SqliteStrategyStore


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


def _guard(mandate: TradingMandate, *, daily_limit_store: DailyLimitStore | None = None) -> OrderGuard:
    broker = MagicMock()
    broker.get_account.return_value = _account()
    # In-memory, per-test-isolated -- the real default path
    # (DEFAULT_DAILY_LIMIT_DB_PATH, under the developer's home dir) would
    # otherwise be shared (and polluted) across every test using this
    # helper, none of which override it.
    return OrderGuard(
        mandate=mandate, broker=broker,
        daily_limit_store=daily_limit_store or DailyLimitStore(":memory:"),
    )


class TestKillSwitchScope:
    """Phase 3 (New-talk-agents/new-thinking/new-restructure/phases/
    phase-3-kill-switch/): OrderGuard.check() must pass scope=symbol to
    is_trading_halted() -- before this fix, a symbol-scoped halt never
    actually blocked anything here, only a global one did."""

    def test_global_halt_blocks_any_symbol(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=True) as mock_halted:
            result = guard.check("AAPL", "buy", qty=1, price=100.0)
        assert not result
        assert "halted" in result.reason.lower()
        mock_halted.assert_called_once_with(scope="AAPL")

    def test_no_halt_allows_order(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            result = guard.check("AAPL", "buy", qty=1, price=100.0)
        assert result

    def test_scoped_halt_checked_with_the_real_symbol(self) -> None:
        """Confirms the scope convention (ticker symbol) is actually
        threaded through -- not just that some scope value is passed."""
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        guard = _guard(mandate)

        def fake_halted(scope: str | None = None) -> bool:
            return scope == "MSFT"

        with patch("vinu_agent.broker.order_guard.is_trading_halted", side_effect=fake_halted):
            aapl_result = guard.check("AAPL", "buy", qty=1, price=100.0)
            msft_result = guard.check("MSFT", "buy", qty=1, price=100.0)

        assert aapl_result  # not halted for this scope
        assert not msft_result  # halted for this scope
        assert "halted" in msft_result.reason.lower()


class TestRequireActiveArtifact:
    """Since 0002 (see New-talk-agents/implementation/00-status.md), the
    active-artifact check reads vinu-research's real strategy_store.db
    directly, in-process -- no HTTP, no mocked response envelope. These
    tests use a real SqliteStrategyStore against a tempfile, same
    no-mocking convention already used for AngleStorage's own tests,
    rather than mocking the store's methods."""

    def _store_with_artifact(self, symbol: str, status: ArtifactStatus) -> SqliteStrategyStore:
        tmp = tempfile.mktemp(suffix=".db")
        store = SqliteStrategyStore(Path(tmp))
        artifact = Artifact.create("strategy", "test-strategy", universe=[symbol])
        artifact.status = status
        store.upsert_artifact(artifact)
        return store

    def test_rejects_when_no_active_artifact_for_symbol(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0)
        guard = _guard(mandate)
        store = self._store_with_artifact("MSFT", ArtifactStatus.ACTIVE)

        with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=store):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert not result
        assert "ACTIVE strategy artifact" in result.reason

    def test_allows_when_active_artifact_covers_symbol(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0)
        guard = _guard(mandate)
        store = self._store_with_artifact("AAPL", ArtifactStatus.ACTIVE)

        with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=store):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert result

    def test_rejects_when_artifact_exists_but_not_active(self) -> None:
        """A CREATED/BENCHING artifact for the symbol shouldn't count --
        only ACTIVE has cleared the promotion gate."""
        mandate = TradingMandate(max_position_pct=1.0)
        guard = _guard(mandate)
        store = self._store_with_artifact("AAPL", ArtifactStatus.BENCHING)

        with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=store):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert not result

    def test_disabled_via_mandate_skips_check(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        guard = _guard(mandate)

        with patch("vinu_agent.broker.research_link.get_strategy_store") as mock_get_store:
            result = guard.check("AAPL", "buy", qty=10, price=100.0)

        mock_get_store.assert_not_called()
        assert result

    def test_fails_open_when_store_raises(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0)
        guard = _guard(mandate)

        with patch(
            "vinu_agent.broker.research_link.get_strategy_store",
            side_effect=OSError("db unavailable"),
        ):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert result


class TestRequireMarketOpen:
    def test_rejects_when_market_closed(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        broker.get_clock.return_value = {"is_open": False, "next_open": "2026-07-21T13:30:00Z"}
        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"))

        result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert not result
        assert "Market is closed" in result.reason

    def test_allows_when_market_open(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        broker.get_clock.return_value = {"is_open": True}
        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"))

        result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert result

    def test_disabled_via_mandate_skips_clock_call(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, require_market_open=False)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"))

        result = guard.check("AAPL", "buy", qty=10, price=100.0)

        broker.get_clock.assert_not_called()
        assert result

    def test_fails_open_when_clock_call_errors(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        broker.get_clock.side_effect = ConnectionError("down")
        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"))

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


class TestDailyLimits:
    """The real bug found and fixed while evaluating OrderGuard's other
    gates for check-then-act races (kill-switch race fix's follow-up
    note): OrderGuard used to store daily counts in a plain in-process
    dict, but is constructed FRESH on every trade_tool.py execute() call
    -- so max_daily_orders/max_daily_trade_volume could never actually
    trigger. These tests construct a fresh OrderGuard per check/pre_
    approve call, same as production, sharing one DailyLimitStore across
    them -- proving the fix, not just that the store itself works
    (test_daily_limits.py already covers that directly)."""

    def test_max_daily_orders_enforced_across_fresh_orderguard_instances(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_daily_orders=2,
        )
        store = DailyLimitStore(":memory:")
        broker = MagicMock()
        broker.get_account.return_value = _account()

        for _ in range(2):
            guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
            result = guard.pre_approve("AAPL", "buy", qty=10, price=100.0)
            assert result

        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        result = guard.check("AAPL", "buy", qty=10, price=100.0)
        assert not result
        assert "Daily order limit" in result.reason

    def test_max_daily_trade_volume_enforced_across_fresh_orderguard_instances(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_daily_trade_volume=1500.0,
        )
        store = DailyLimitStore(":memory:")
        broker = MagicMock()
        broker.get_account.return_value = _account()

        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        assert guard.pre_approve("AAPL", "buy", qty=10, price=100.0)  # value 1000

        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        result = guard.check("AAPL", "buy", qty=10, price=100.0)  # would bring total to 2000 > 1500
        assert not result
        assert "max_daily_trade_volume" in result.reason

    def test_check_alone_does_not_increment_the_count(self) -> None:
        """Only pre_approve() (the point immediately before a real
        submission) increments -- a plain check() (e.g. a dry-run/
        preview) must not consume the daily budget."""
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_daily_orders=1,
        )
        store = DailyLimitStore(":memory:")
        broker = MagicMock()
        broker.get_account.return_value = _account()

        for _ in range(5):
            guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
            assert result

    def test_symbols_tracked_independently(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_daily_orders=1,
        )
        store = DailyLimitStore(":memory:")
        broker = MagicMock()
        broker.get_account.return_value = _account()

        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        assert guard.pre_approve("AAPL", "buy", qty=10, price=100.0)

        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        result = guard.check("MSFT", "buy", qty=10, price=100.0)
        assert result  # MSFT's own count is still 0


class TestMaxCapitalUtilization:
    def test_rejects_when_projected_utilization_exceeds_cap(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, max_capital_utilization_pct=0.6, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account(equity=100_000.0, cash=50_000.0)
        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"))

        result = guard.check("AAPL", "buy", qty=200, price=100.0)

        assert not result
        assert "max_capital_utilization_pct" in result.reason

    def test_allows_when_within_cap(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, max_capital_utilization_pct=0.6, require_active_artifact=False)
        broker = MagicMock()
        broker.get_account.return_value = _account(equity=100_000.0, cash=90_000.0)
        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"))

        result = guard.check("AAPL", "buy", qty=10, price=100.0)

        assert result
