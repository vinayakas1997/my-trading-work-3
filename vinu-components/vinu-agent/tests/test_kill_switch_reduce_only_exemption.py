"""Scenario 07 (the-reasoning-inefficiency/scenarios-test/
07-agent-kill-switch-enforcement/scenario.md) -- the gap flagged while
building vinu-live's scenario 02: that scenario could only prove the
orchestrator's own local halted-flag handling, not the actual
authoritative enforcement at OrderGuard.check(), reached over
/agent/broker/order. test_order_guard.py's TestKillSwitchScope mocks
is_trading_halted() for every test, and only ONE test there ever sets it
True (test_global_halt_blocks_any_symbol) -- and that one only exercises
a plain buy, never reduce_only. No existing test combined
is_trading_halted()==True with reduce_only=True, the exact exemption this
proves.

Goes one step past that file's own mocking convention: uses the REAL
halt_trading()/resume_trading() (the actual filesystem-backed global kill
switch, /tmp/vinu-trading-halt) against a real OrderGuard instance -- the
most authentic version of this claim reachable without a live broker.
Reuses test_kill_switch.py's own safe clean-up fixture pattern so this
test never leaves the real switch engaged for anything else on the
machine.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vinu_agent.broker.alpaca import Account
from vinu_agent.broker.daily_limits import DailyLimitStore
from vinu_agent.broker.guard_codes import ReasonCode
from vinu_agent.broker.kill_switch import halt_trading, resume_trading
from vinu_agent.broker.mandate import TradingMandate
from vinu_agent.broker.order_guard import OrderGuard


@pytest.fixture(autouse=True)
def _isolated_safety_ledger(tmp_path):
    # halt_trading()/resume_trading() append to the safety ledger --
    # point it at a tmp file so this doesn't write to the real
    # ~/.vinu/safety_ledger.jsonl (same as test_kill_switch.py).
    from vinu_agent.broker.audit_ledger import HashChainedLedger, reset_safety_ledger

    reset_safety_ledger(HashChainedLedger(tmp_path / "safety_ledger.jsonl"))
    yield
    reset_safety_ledger(None)


@pytest.fixture(autouse=True)
def _clean_kill_switch_state():
    # Never leave the REAL global kill switch engaged, even if a test
    # fails mid-way -- same pattern test_kill_switch.py already uses.
    resume_trading()
    yield
    resume_trading()


@pytest.fixture(autouse=True)
def _isolated_override_store():
    from vinu_agent.broker.symbol_overrides import SymbolOverrideStore, reset_override_store

    reset_override_store(SymbolOverrideStore(":memory:"))
    yield
    reset_override_store(None)


@pytest.fixture(autouse=True)
def _isolated_limit_store():
    from vinu_agent.broker.symbol_limits import SymbolLimitStore, reset_limit_store

    reset_limit_store(SymbolLimitStore(":memory:"))
    yield
    reset_limit_store(None)


def _account() -> Account:
    return Account(
        account_id="test", status="ACTIVE", currency="USD",
        cash=100_000.0, portfolio_value=100_000.0, buying_power=100_000.0,
        equity=100_000.0, daytrade_count=0, pattern_day_trader=False,
    )


def _guard() -> OrderGuard:
    # max_position_pct=1.0 + require_active_artifact=False + allow_short:
    # the only thing gating these orders is the kill switch, nothing else
    # in the mandate (a reduce_only sell with no matching broker position
    # on record reads as a short otherwise, an unrelated mandate check
    # this scenario isn't about).
    mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False, allow_short=True)
    broker = MagicMock()
    broker.get_account.return_value = _account()
    return OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"))


class TestRealKillSwitchReduceOnlyExemption:
    def test_reduce_only_order_allowed_through_a_real_halt_default_policy(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_LIVE_HALT_POLICY", "entries_only")
        halt_trading()  # the REAL global kill switch file, not mocked
        guard = _guard()

        result = guard.check("AAPL", "sell", qty=5, price=100.0, reduce_only=True)

        assert result.allowed is True

    def test_non_reduce_only_order_blocked_by_a_real_halt_default_policy(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_LIVE_HALT_POLICY", "entries_only")
        halt_trading()
        guard = _guard()

        result = guard.check("AAPL", "buy", qty=5, price=100.0, reduce_only=False)

        assert result.allowed is False
        assert result.code == ReasonCode.KILL_SWITCH_HALT

    def test_reduce_only_exemption_itself_is_policy_gated_not_unconditional(self, monkeypatch) -> None:
        """The exemption is "entries_only" as a POLICY choice, not
        "reduce_only always bypasses the kill switch" -- proves the
        policy actually controls it rather than reduce_only=True being an
        unconditional bypass no matter what VINU_LIVE_HALT_POLICY says."""
        monkeypatch.setenv("VINU_LIVE_HALT_POLICY", "always")
        halt_trading()
        guard = _guard()

        result = guard.check("AAPL", "sell", qty=5, price=100.0, reduce_only=True)

        assert result.allowed is False
        assert result.code == ReasonCode.KILL_SWITCH_HALT

    def test_no_halt_allows_both_kinds_of_order(self, monkeypatch) -> None:
        """Sanity control: with the real switch genuinely off, neither
        case is blocked by it -- confirms the two blocked cases above are
        actually caused by the halt, not some other mandate check."""
        monkeypatch.setenv("VINU_LIVE_HALT_POLICY", "entries_only")
        guard = _guard()

        entry = guard.check("AAPL", "buy", qty=5, price=100.0, reduce_only=False)
        exit_ = guard.check("AAPL", "sell", qty=5, price=100.0, reduce_only=True)

        assert entry.allowed is True
        assert exit_.allowed is True
