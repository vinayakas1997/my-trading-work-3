"""Tests for check_rebalance_allowed -- Phase 3's ready-to-use gate for
Phase 5's not-yet-built rebalancer. See agent/rebalance_guard.py.
"""

from __future__ import annotations

from unittest.mock import patch

from vinu_agent.agent.rebalance_guard import check_rebalance_allowed


class TestCheckRebalanceAllowed:
    def test_allowed_when_not_halted(self) -> None:
        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=False):
            assert check_rebalance_allowed("AAPL") is True

    def test_blocked_when_halted_for_scope(self) -> None:
        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=True):
            assert check_rebalance_allowed("AAPL") is False

    def test_scope_passed_through_exactly(self) -> None:
        with patch("vinu_agent.broker.kill_switch.is_trading_halted", return_value=False) as mock_halted:
            check_rebalance_allowed("MSFT")
        mock_halted.assert_called_once_with(scope="MSFT")

    def test_check_error_fails_closed_to_blocked(self) -> None:
        with patch("vinu_agent.broker.kill_switch.is_trading_halted", side_effect=ConnectionError("down")):
            assert check_rebalance_allowed("AAPL") is False
