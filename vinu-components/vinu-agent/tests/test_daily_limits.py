"""Tests for DailyLimitStore -- the real, persistent daily order-count/
volume tracker that closes OrderGuard's non-functioning max_daily_orders/
max_daily_trade_volume checks (found while evaluating OrderGuard's other
gates for check-then-act races, per the kill-switch race fix's own
follow-up note). See broker/daily_limits.py's module docstring.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.broker.daily_limits import DailyLimitStore


@pytest.fixture
def db_path() -> Path:
    path = Path(tempfile.mktemp(suffix=".db"))
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def store(db_path: Path) -> DailyLimitStore:
    s = DailyLimitStore(db_path)
    yield s
    s.close()


class TestDailyLimitStore:
    def test_starts_at_zero(self, store: DailyLimitStore) -> None:
        assert store.count_today("AAPL") == 0
        assert store.volume_today("AAPL") == 0.0

    def test_record_order_increments_count_and_volume(self, store: DailyLimitStore) -> None:
        store.record_order("AAPL", 5000.0)
        assert store.count_today("AAPL") == 1
        assert store.volume_today("AAPL") == 5000.0

    def test_repeated_orders_accumulate(self, store: DailyLimitStore) -> None:
        for _ in range(3):
            store.record_order("AAPL", 1000.0)
        assert store.count_today("AAPL") == 3
        assert store.volume_today("AAPL") == 3000.0

    def test_symbols_are_independent(self, store: DailyLimitStore) -> None:
        store.record_order("AAPL", 1000.0)
        store.record_order("MSFT", 2000.0)
        assert store.count_today("AAPL") == 1
        assert store.volume_today("AAPL") == 1000.0
        assert store.count_today("MSFT") == 1
        assert store.volume_today("MSFT") == 2000.0


class TestDailyLimitStorePersistsAcrossInstances:
    """The actual bug being closed: OrderGuard is constructed fresh on
    every trade_tool.py execute() call -- counts recorded by one
    DailyLimitStore instance must be visible to a second instance pointed
    at the same on-disk path, not just to the instance that wrote them."""

    def test_an_order_recorded_by_one_instance_is_visible_to_another(self, db_path: Path) -> None:
        writer = DailyLimitStore(db_path)
        writer.record_order("AAPL", 5000.0)
        writer.close()

        reader = DailyLimitStore(db_path)
        count, volume = reader.count_today("AAPL"), reader.volume_today("AAPL")
        reader.close()

        assert count == 1
        assert volume == 5000.0

    def test_ten_fresh_instances_accumulate_like_one_long_lived_one(self, db_path: Path) -> None:
        """Mirrors the real production shape: a brand-new OrderGuard (and
        therefore a brand-new DailyLimitStore-backed count) on every
        single order submission."""
        for _ in range(10):
            s = DailyLimitStore(db_path)
            s.record_order("AAPL", 100.0)
            s.close()

        final = DailyLimitStore(db_path)
        try:
            assert final.count_today("AAPL") == 10
            assert final.volume_today("AAPL") == 1000.0
        finally:
            final.close()
