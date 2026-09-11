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


@pytest.fixture(autouse=True)
def _isolated_override_store():
    # C4: OrderGuard.check() now consults the per-symbol override store
    # (lazy singleton at ~/.vinu). Point it at an in-memory DB so these
    # tests neither touch the real file nor leak state between tests.
    from vinu_agent.broker.symbol_overrides import SymbolOverrideStore, reset_override_store

    reset_override_store(SymbolOverrideStore(":memory:"))
    yield
    reset_override_store(None)


@pytest.fixture(autouse=True)
def _isolated_limit_store():
    # C7: same reasoning as _isolated_override_store above, for the
    # per-symbol limit-value store `_effective_limit()` now consults.
    from vinu_agent.broker.symbol_limits import SymbolLimitStore, reset_limit_store

    reset_limit_store(SymbolLimitStore(":memory:"))
    yield
    reset_limit_store(None)


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


class TestOrderThrottle:
    """Stage A (A15): the sub-second order-rate breaker (B20). Rate and
    window are env-configurable now; a tripped throttle logs at WARNING."""

    def test_trips_at_the_configured_rate(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        guard = _guard(mandate)
        guard._throttle_limit_per_sec = 3
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            assert guard.check("AAPL", "buy", qty=1, price=10.0)
            assert guard.check("AAPL", "buy", qty=1, price=10.0)
            assert guard.check("AAPL", "buy", qty=1, price=10.0)
            blocked = guard.check("AAPL", "buy", qty=1, price=10.0)
        assert not blocked
        assert "throttle" in blocked.reason.lower()

    def test_rate_and_window_read_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_AGENT_ORDER_THROTTLE_PER_SEC", "42")
        monkeypatch.setenv("VINU_AGENT_ORDER_THROTTLE_WINDOW_SEC", "2.5")
        guard = _guard(TradingMandate(require_active_artifact=False))
        assert guard._throttle_limit_per_sec == 42
        assert guard._throttle_window_sec == 2.5

    def test_tripped_throttle_logs_a_warning(self, caplog) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        guard = _guard(mandate)
        guard._throttle_limit_per_sec = 1
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            guard.check("AAPL", "buy", qty=1, price=10.0)
            with caplog.at_level("WARNING", logger="vinu_agent.broker.order_guard"):
                guard.check("AAPL", "buy", qty=1, price=10.0)
        assert any("throttle tripped" in r.message.lower() for r in caplog.records)


class TestOrderValueDetermination:
    """Stage A (A36): notional cap uses max(estimated_value, qty*price) and
    fails closed when neither yields a usable number (Vibe-Trading)."""

    def test_takes_the_larger_of_estimated_value_and_qty_price(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, max_order_value=5_000.0)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            # estimated_value understates it (1000) but qty*price is 10*800=8000 > cap
            result = guard.check("AAPL", "buy", qty=10, price=800.0, estimated_value=1_000.0)
        assert not result
        assert "exceeds max_order_value" in result.reason

    def test_unpriceable_entry_is_rejected(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            result = guard.check("AAPL", "buy", qty=10)  # no price, no estimated_value
        assert not result
        assert "Cannot determine order value" in result.reason

    def test_unpriceable_reduce_only_is_allowed_through(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, allow_short=True)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            result = guard.check("AAPL", "sell", qty=10, reduce_only=True)
        assert result  # risk-reducing orders are exempt, same as the other gates

    def test_priced_entry_within_cap_passes(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, max_order_value=50_000.0)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            assert guard.check("AAPL", "buy", qty=10, price=100.0)


class TestReasonCodesAndReauth:
    """Stage C (C9/C17): every rejection carries a machine `code`, and a
    near-limit order gets a PAUSE_FOR_REAUTH outcome, not a flat reject."""

    def test_rejection_carries_a_reason_code(self) -> None:
        from vinu_agent.broker.guard_codes import GuardOutcome, ReasonCode

        mandate = TradingMandate(require_active_artifact=False, allowed_tickers={"MSFT"})
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            r = guard.check("AAPL", "buy", qty=1, price=10.0)
        assert not r
        assert r.code == ReasonCode.TICKER_NOT_ALLOWED
        assert r.outcome == GuardOutcome.REJECT
        assert r.needs_reauth is False

    def test_allow_result_has_ok_code(self) -> None:
        from vinu_agent.broker.guard_codes import GuardOutcome, ReasonCode

        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            r = guard.check("AAPL", "buy", qty=1, price=10.0)
        assert r
        assert r.code == ReasonCode.OK
        assert r.outcome == GuardOutcome.ALLOW

    def test_near_max_order_value_pauses_for_reauth(self, monkeypatch) -> None:
        from vinu_agent.broker import order_guard as og
        from vinu_agent.broker.guard_codes import GuardOutcome, ReasonCode

        monkeypatch.setattr(og, "REAUTH_BAND_FRACTION", 0.9)
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, max_order_value=10_000.0)
        guard = og.OrderGuard(mandate=mandate, broker=_guard(mandate)._broker,
                              daily_limit_store=DailyLimitStore(":memory:"))
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            # 9_500 is inside [9_000, 10_000] -> pause, not allow, not reject
            r = guard.check("AAPL", "buy", qty=95, price=100.0)
        assert r.outcome == GuardOutcome.PAUSE_FOR_REAUTH
        assert r.code == ReasonCode.NEAR_MAX_ORDER_VALUE
        assert bool(r) is False           # a bool-only caller still fails safe
        assert r.needs_reauth is True

    def test_over_the_hard_limit_still_hard_rejects(self, monkeypatch) -> None:
        from vinu_agent.broker import order_guard as og
        from vinu_agent.broker.guard_codes import GuardOutcome, ReasonCode

        monkeypatch.setattr(og, "REAUTH_BAND_FRACTION", 0.9)
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, max_order_value=10_000.0)
        guard = og.OrderGuard(mandate=mandate, broker=_guard(mandate)._broker,
                              daily_limit_store=DailyLimitStore(":memory:"))
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            r = guard.check("AAPL", "buy", qty=200, price=100.0)  # 20_000 > 10_000
        assert r.outcome == GuardOutcome.REJECT
        assert r.code == ReasonCode.MAX_ORDER_VALUE

    def test_reauth_band_disabled_by_default(self) -> None:
        from vinu_agent.broker import order_guard as og
        from vinu_agent.broker.guard_codes import GuardOutcome

        assert og.REAUTH_BAND_FRACTION == 1.0
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, max_order_value=10_000.0)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            r = guard.check("AAPL", "buy", qty=99, price=100.0)  # 9_900, just under
        assert r.outcome == GuardOutcome.ALLOW


class TestMandateConsentExpiry:
    """Stage C (C18): a stale mandate stops permitting new/increasing positions."""

    def _mandate(self, expires_at: str) -> TradingMandate:
        return TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, allow_short=True,
            consent_expires_at=expires_at,
        )

    def test_consent_expired_helper(self) -> None:
        from datetime import datetime, timedelta, timezone

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        assert self._mandate(past).consent_expired() is True
        assert self._mandate(future).consent_expired() is False
        assert self._mandate("").consent_expired() is False
        assert self._mandate("not-a-date").consent_expired() is False  # ignored, not crash

    def test_expired_mandate_blocks_an_entry(self) -> None:
        from datetime import datetime, timedelta, timezone
        from vinu_agent.broker.guard_codes import ReasonCode

        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        guard = _guard(self._mandate(past))
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            r = guard.check("AAPL", "buy", qty=1, price=10.0)
        assert not r
        assert r.code == ReasonCode.MANDATE_EXPIRED

    def test_expired_mandate_still_allows_reduce_only(self) -> None:
        from datetime import datetime, timedelta, timezone

        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        guard = _guard(self._mandate(past))
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            r = guard.check("AAPL", "sell", qty=1, price=10.0, reduce_only=True)
        assert r  # de-risking is never blocked by expiry

    def test_unexpired_mandate_is_a_pass_through(self) -> None:
        from datetime import datetime, timedelta, timezone

        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        guard = _guard(self._mandate(future))
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            assert guard.check("AAPL", "buy", qty=1, price=10.0)


class TestPositionSizeMultiplier:
    """Stage C (C8): a [0,1] scalar that shrinks an order to fit the soft
    quantitative limits, instead of a hard reject."""

    def _guard(self, mandate, *, equity=100_000.0, cash=100_000.0):
        broker = MagicMock()
        broker.get_account.return_value = _account(equity=equity, cash=cash)
        g = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"))
        # no risk-budget service in these tests
        g._risk_budget_multiplier = lambda symbol: None
        return g

    def test_no_binding_limit_gives_multiplier_one(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, max_order_value=1_000_000.0)
        g = self._guard(mandate)
        m = g.position_size_multiplier("AAPL", "buy", qty=10, price=100.0)
        assert m.multiplier == 1.0
        assert m.binding is None

    def test_max_order_value_scales_the_order_down(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, max_order_value=5_000.0)
        g = self._guard(mandate)
        m = g.position_size_multiplier("AAPL", "buy", qty=100, price=100.0)  # value 10_000, cap 5_000
        assert m.multiplier == pytest.approx(0.5)
        assert m.binding == "max_order_value"

    def test_min_of_several_limits_wins(self) -> None:
        # max_order_value -> 0.5 ; max_position_pct 0.10 of 100k equity on a
        # 10_000 order -> frac 0.10, cap 0.10 -> 1.0 ; so 0.5 binds.
        mandate = TradingMandate(max_position_pct=0.10, max_order_value=5_000.0)
        g = self._guard(mandate)
        m = g.position_size_multiplier("AAPL", "buy", qty=100, price=100.0)
        assert m.multiplier == pytest.approx(0.5)
        assert set(m.components) >= {"max_order_value", "max_position_pct"}

    def test_capital_utilization_headroom_limits_size(self) -> None:
        # 60% cap, 55% already deployed -> 5% of 100k = 5_000 headroom for a
        # 10_000 order -> 0.5
        mandate = TradingMandate(max_position_pct=1.0, max_order_value=1e9,
                                 max_capital_utilization_pct=0.60)
        g = self._guard(mandate, equity=100_000.0, cash=45_000.0)  # deployed = 55_000
        m = g.position_size_multiplier("AAPL", "buy", qty=100, price=100.0)
        assert m.multiplier == pytest.approx(0.5)
        assert m.binding == "max_capital_utilization"

    def test_risk_budget_multiplier_is_folded_in(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, max_order_value=1e9)
        g = self._guard(mandate)
        g._risk_budget_multiplier = lambda symbol: 0.25
        m = g.position_size_multiplier("AAPL", "buy", qty=10, price=100.0)
        assert m.multiplier == pytest.approx(0.25)
        assert m.binding == "risk_budget"

    def test_soft_limits_disabled_by_default(self) -> None:
        from vinu_agent.broker import order_guard as og

        assert og.SOFT_LIMITS_ENABLED is False


class TestSymbolOverrides:
    """Stage C (C4): per-symbol operator override, ahead of the mandate."""

    def _guard_with_overrides(self, store):
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, allow_short=True)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        return OrderGuard(
            mandate=mandate, broker=broker,
            daily_limit_store=DailyLimitStore(":memory:"), override_store=store,
        )

    def test_untradeable_blocks_every_order_with_the_operator_reason(self) -> None:
        from vinu_agent.broker.guard_codes import OverrideState, ReasonCode
        from vinu_agent.broker.symbol_overrides import SymbolOverrideStore

        store = SymbolOverrideStore(":memory:")
        store.set("AAPL", OverrideState.UNTRADEABLE, reason="pending 8-K", set_by="alice")
        guard = self._guard_with_overrides(store)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            r = guard.check("AAPL", "buy", qty=1, price=10.0)
        assert not r
        assert r.code == ReasonCode.OVERRIDE_UNTRADEABLE
        assert "pending 8-K" in r.reason and "alice" in r.reason

    def test_reduce_only_override_blocks_entries_but_allows_exits(self) -> None:
        from vinu_agent.broker.guard_codes import OverrideState, ReasonCode
        from vinu_agent.broker.symbol_overrides import SymbolOverrideStore

        store = SymbolOverrideStore(":memory:")
        store.set("AAPL", OverrideState.REDUCE_ONLY, reason="de-risking")
        guard = self._guard_with_overrides(store)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            entry = guard.check("AAPL", "buy", qty=1, price=10.0)
            exit_ = guard.check("AAPL", "sell", qty=1, price=10.0, reduce_only=True)
        assert not entry and entry.code == ReasonCode.OVERRIDE_REDUCE_ONLY
        assert exit_  # risk-reducing order clears

    def test_no_override_is_a_pass_through(self) -> None:
        from vinu_agent.broker.symbol_overrides import SymbolOverrideStore

        guard = self._guard_with_overrides(SymbolOverrideStore(":memory:"))
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            assert guard.check("AAPL", "buy", qty=1, price=10.0)

    def test_override_store_failure_fails_open(self) -> None:
        broken = MagicMock()
        broken.get.side_effect = RuntimeError("db gone")
        guard = self._guard_with_overrides(broken)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            assert guard.check("AAPL", "buy", qty=1, price=10.0)  # allowed despite the store error


class TestSymbolLimitOverrides:
    """Stage C (C7): per-symbol *limit-value* override, replacing the
    mandate's global default wherever check()/position_size_multiplier()
    reads it."""

    def _guard_with_limits(self, store, mandate=None):
        mandate = mandate or TradingMandate(max_position_pct=1.0, require_active_artifact=False, max_order_value=50_000.0)
        broker = MagicMock()
        broker.get_account.return_value = _account()
        return OrderGuard(
            mandate=mandate, broker=broker,
            daily_limit_store=DailyLimitStore(":memory:"), limit_store=store,
        )

    def test_tighter_symbol_override_rejects_where_the_mandate_default_would_pass(self) -> None:
        from vinu_agent.broker.guard_codes import ReasonCode
        from vinu_agent.broker.symbol_limits import SymbolLimitStore

        store = SymbolLimitStore(":memory:")
        store.set("AAPL", max_order_value=1_000.0, reason="volatile small-cap")
        guard = self._guard_with_limits(store)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            # 10 * 800 = 8000 -- under the mandate's 50k default, over AAPL's 1k override.
            result = guard.check("AAPL", "buy", qty=10, price=800.0)
        assert not result
        assert result.code == ReasonCode.MAX_ORDER_VALUE
        assert "1000.00" in result.reason

    def test_override_is_per_symbol_not_global(self) -> None:
        from vinu_agent.broker.symbol_limits import SymbolLimitStore

        store = SymbolLimitStore(":memory:")
        store.set("AAPL", max_order_value=1_000.0)
        guard = self._guard_with_limits(store)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            # MSFT has no override -- falls back to the mandate's 50k default.
            assert guard.check("MSFT", "buy", qty=10, price=800.0)

    def test_no_override_falls_back_to_mandate_default(self) -> None:
        from vinu_agent.broker.symbol_limits import SymbolLimitStore

        guard = self._guard_with_limits(SymbolLimitStore(":memory:"))
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            assert guard.check("AAPL", "buy", qty=10, price=800.0)

    def test_limit_store_failure_fails_open_to_mandate_default(self) -> None:
        broken = MagicMock()
        broken.get.side_effect = RuntimeError("db gone")
        guard = self._guard_with_limits(broken)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            assert guard.check("AAPL", "buy", qty=10, price=800.0)  # mandate default (50k) still applies, order passes

    def test_position_size_multiplier_uses_the_tighter_symbol_override(self) -> None:
        from vinu_agent.broker.symbol_limits import SymbolLimitStore

        store = SymbolLimitStore(":memory:")
        store.set("AAPL", max_order_value=500.0)
        guard = self._guard_with_limits(store)
        # value = 10 * 100 = 1000 -- above the 500 override, so it should scale down.
        m = guard.position_size_multiplier("AAPL", "buy", qty=10, price=100.0)
        assert m.multiplier == pytest.approx(0.5)
        assert m.binding == "max_order_value"

    def test_max_position_pct_override_is_effective(self) -> None:
        from vinu_agent.broker.guard_codes import ReasonCode
        from vinu_agent.broker.symbol_limits import SymbolLimitStore

        store = SymbolLimitStore(":memory:")
        store.set("AAPL", max_position_pct=0.01)  # 1% of equity
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, max_order_value=1_000_000.0)
        guard = self._guard_with_limits(store, mandate=mandate)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            # 10 * 800 = 8000 on 100k equity = 8% > AAPL's 1% override.
            result = guard.check("AAPL", "buy", qty=10, price=800.0)
        assert not result
        assert result.code == ReasonCode.MAX_POSITION_PCT

    def test_clear_removes_the_override(self) -> None:
        from vinu_agent.broker.symbol_limits import SymbolLimitStore

        store = SymbolLimitStore(":memory:")
        store.set("AAPL", max_order_value=1_000.0)
        store.clear("AAPL")
        guard = self._guard_with_limits(store)
        with patch("vinu_agent.broker.order_guard.is_trading_halted", return_value=False):
            assert guard.check("AAPL", "buy", qty=10, price=800.0)  # back to mandate's 50k default


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
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"symbols": []}
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp) as mock_get:
            result = guard.check("AAPL", "sell", qty=10, price=100.0)
        # Concentration only ever calls /portfolio/state and only for buys;
        # the one call seen here is _check_risk_budget's /portfolio/risk/status
        # (Stage 2 #22), which runs for any non-reduce_only order regardless
        # of side -- a "sell" with no open position to reduce is a short
        # entry, which is still new/increasing exposure.
        called_urls = [c.args[0] for c in mock_get.call_args_list]
        assert all("/portfolio/state" not in u for u in called_urls)
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
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"symbols": []}
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp) as mock_get:
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        # Concentration itself is disabled (default mandate thresholds are
        # 1.0) and must not call /portfolio/state; the risk-budget check
        # (Stage 2 #22) is unconditional and does call /portfolio/risk/status.
        called_urls = [c.args[0] for c in mock_get.call_args_list]
        assert all("/portfolio/state" not in u for u in called_urls)
        assert result


class TestRiskBudget:
    """Stage 2 (how-to-make-it-live.md #22): vinu-portfolio's
    compute_risk_budget() correctly computes a TIER_HALT / halted status per
    symbol, but nothing enforced it -- it was a dashboard number, not a
    guard. These prove OrderGuard now actually reads and acts on it."""

    def test_blocks_new_order_for_halted_symbol(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, require_market_open=False)
        guard = _guard(mandate)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "symbols": [{"symbol": "AAPL", "halted": True, "daily_pnl_pct": -3.2}],
        }
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        assert not result
        assert "TIER_HALT" in result.reason

    def test_allows_order_for_non_halted_symbol(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, require_market_open=False)
        guard = _guard(mandate)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "symbols": [{"symbol": "AAPL", "halted": False, "daily_pnl_pct": -0.5}],
        }
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        assert result

    def test_reduce_only_bypasses_halted_symbol(self) -> None:
        """The whole point of TIER_HALT is to stop digging the hole deeper --
        it must never block an order that's shrinking exposure on the
        already-halted symbol, same posture as the kill-switch reduce_only
        exemption (Scenario 21)."""
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False, allow_short=True,
        )
        guard = _guard(mandate)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "symbols": [{"symbol": "AAPL", "halted": True, "daily_pnl_pct": -3.2}],
        }
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp) as mock_get:
            result = guard.check("AAPL", "sell", qty=10, price=100.0, reduce_only=True)
        mock_get.assert_not_called()
        assert result

    def test_fails_open_on_lookup_error(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, require_market_open=False)
        guard = _guard(mandate)
        with patch("vinu_agent.broker.order_guard.requests.get", side_effect=ConnectionError("down")):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
        assert result

    def test_ignores_other_symbols_in_the_budget(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, require_market_open=False)
        guard = _guard(mandate)
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "symbols": [{"symbol": "MSFT", "halted": True, "daily_pnl_pct": -3.2}],
        }
        with patch("vinu_agent.broker.order_guard.requests.get", return_value=resp):
            result = guard.check("AAPL", "buy", qty=10, price=100.0)
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


class TestPortfolioDailyOrderCap:
    """Stage 2 (how-to-make-it-live.md #8): max_daily_orders above is
    per-symbol only -- 10/symbol x N traded symbols has no ceiling of its
    own without this. Same fresh-OrderGuard-per-call shape as
    TestDailyLimits above, sharing one DailyLimitStore."""

    def test_disabled_by_default(self) -> None:
        mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, require_market_open=False)
        store = DailyLimitStore(":memory:")
        broker = MagicMock()
        broker.get_account.return_value = _account()

        for symbol in ("AAPL", "MSFT", "NVDA", "GOOG"):
            guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
            assert guard.pre_approve(symbol, "buy", qty=1, price=100.0)

    def test_blocks_once_total_across_symbols_is_reached(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_daily_orders=10, max_daily_orders_portfolio=3,
        )
        store = DailyLimitStore(":memory:")
        broker = MagicMock()
        broker.get_account.return_value = _account()

        for symbol in ("AAPL", "MSFT", "NVDA"):
            guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
            assert guard.pre_approve(symbol, "buy", qty=1, price=100.0)

        # a 4th symbol, none of them individually anywhere near
        # max_daily_orders=10 -- only the portfolio-wide total blocks this
        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        result = guard.check("GOOG", "buy", qty=1, price=100.0)
        assert not result
        assert "Portfolio-wide daily order limit" in result.reason

    def test_reduce_only_bypasses_the_cap(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            allow_short=True, max_daily_orders=10, max_daily_orders_portfolio=1,
        )
        store = DailyLimitStore(":memory:")
        broker = MagicMock()
        broker.get_account.return_value = _account()

        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        assert guard.pre_approve("AAPL", "buy", qty=1, price=100.0)  # uses up the cap of 1

        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        result = guard.check("MSFT", "sell", qty=1, price=100.0, reduce_only=True)
        assert result

    def test_new_order_still_blocked_once_cap_reached(self) -> None:
        mandate = TradingMandate(
            max_position_pct=1.0, require_active_artifact=False, require_market_open=False,
            max_daily_orders=10, max_daily_orders_portfolio=1,
        )
        store = DailyLimitStore(":memory:")
        broker = MagicMock()
        broker.get_account.return_value = _account()

        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        assert guard.pre_approve("AAPL", "buy", qty=1, price=100.0)

        guard = OrderGuard(mandate=mandate, broker=broker, daily_limit_store=store)
        result = guard.check("MSFT", "buy", qty=1, price=100.0)
        assert not result


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
