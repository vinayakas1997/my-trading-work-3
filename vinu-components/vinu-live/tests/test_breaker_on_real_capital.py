"""The breaker's percentage limits are measured against the real-money base, not the paper balance."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from tests.test_scheduler_allocation_and_ownership import _sched
from vinu_live.book.positions import open_position
from vinu_live.scheduler import LiveScheduler


def _check(s, portfolio_value=96_000.0, broker_positions=None):
    s._engage_real_halt = AsyncMock()
    # the shared test scheduler stubs _check_breaker to always allow; call the real method
    return asyncio.run(LiveScheduler._check_breaker(s, portfolio_value, broker_positions=broker_positions))


def test_a_loss_that_is_small_on_the_paper_balance_halts_a_twenty_dollar_account(tmp_path, monkeypatch):
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    s = _sched(tmp_path, twap_slices=1)
    open_position(s._book, "AAA", "long", 2.0, 5.0)           # 10 dollars at cost
    s._fetch_prices = AsyncMock(return_value={"AAA": 3.0})     # down 4 dollars: 20 percent of 20, 0.004 percent of 96,000
    verdict, reason = _check(s)
    assert verdict == "HALT" and "daily" in (reason or "").lower()


def test_without_a_capital_base_the_same_loss_is_a_rounding_error(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_REAL_CAPITAL", raising=False)
    s = _sched(tmp_path, twap_slices=1)
    open_position(s._book, "AAA", "long", 2.0, 5.0)
    s._fetch_prices = AsyncMock(return_value={"AAA": 3.0})
    verdict, _ = _check(s, broker_positions={"AAA": 2.0})
    assert verdict != "HALT"


def test_only_the_systems_own_positions_count_not_the_rest_of_the_paper_account(tmp_path, monkeypatch):
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    s = _sched(tmp_path, twap_slices=1)
    s._fetch_prices = AsyncMock(return_value={"HELD": 1000.0})
    verdict, _ = _check(s, broker_positions={"HELD": 500.0})  # 500,000 dollars of someone else's holding
    assert verdict != "HALT"
