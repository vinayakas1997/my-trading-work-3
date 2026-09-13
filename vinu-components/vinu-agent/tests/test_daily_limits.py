"""Tests for DailyLimitStore -- the real, persistent daily order-count/
volume tracker that closes OrderGuard's non-functioning max_daily_orders/
max_daily_trade_volume checks (found while evaluating OrderGuard's other
gates for check-then-act races, per the kill-switch race fix's own
follow-up note). See broker/daily_limits.py's module docstring.
"""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path

import pytest

from vinu_agent.broker.daily_limits import DailyLimitStore


@pytest.fixture
def db_path() -> Path:
    path = Path(tempfile.mktemp(suffix=".db"))
    yield path
    # Windows can hold the file handle open for a while after a thread's
    # sqlite3.Connection.close() returns (WAL's -shm/-wal sidecars in
    # particular) -- only observed here, at fixture teardown, after tests
    # that open many concurrent connections. Not a correctness issue (every
    # test's own assertions already passed by this point) and not worth
    # failing the test run over -- these are throwaway tempfiles the OS
    # reclaims regardless. Best-effort cleanup only.
    for _ext in ("", "-wal", "-shm"):
        p = Path(str(path) + _ext)
        for attempt in range(10):
            try:
                p.unlink(missing_ok=True)
                break
            except PermissionError:
                if attempt == 9:
                    break
                time.sleep(0.1)


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


class TestCountTodayTotal:
    """Stage 2 (how-to-make-it-live.md #8): max_daily_orders is per-symbol
    only -- 10/symbol x N traded symbols has no ceiling of its own without
    this."""

    def test_zero_with_no_orders(self, store: DailyLimitStore) -> None:
        assert store.count_today_total() == 0

    def test_sums_across_symbols(self, store: DailyLimitStore) -> None:
        store.record_order("AAPL", 1000.0)
        store.record_order("AAPL", 1000.0)
        store.record_order("MSFT", 2000.0)
        store.record_order("NVDA", 3000.0)
        assert store.count_today_total() == 4

    def test_matches_sum_of_per_symbol_counts(self, store: DailyLimitStore) -> None:
        for _ in range(3):
            store.record_order("AAPL", 100.0)
        for _ in range(2):
            store.record_order("MSFT", 100.0)
        assert store.count_today_total() == store.count_today("AAPL") + store.count_today("MSFT")


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


class TestRecordOrderUnderRealConcurrency:
    """situation-test/01-daily-order-limit-race.md: 30 threads racing
    record_order() for the same symbol against a real, shared, on-disk
    SQLite store used to mostly crash with unhandled
    sqlite3.OperationalError ("database is locked") or
    sqlite3.IntegrityError ("UNIQUE constraint failed") from the old
    SELECT-then-INSERT/UPDATE logic -- a real bug, not just a narrow race
    window, since it fired on nearly every run. Each thread opens its own
    DailyLimitStore instance (own thread-local sqlite3 connection, same
    on-disk file) to mirror the real shape: a fresh OrderGuard/
    DailyLimitStore per trade_tool.py execute() call, per-thread in a real
    server."""

    def test_thirty_concurrent_orders_all_succeed_with_correct_final_count(
        self, db_path: Path
    ) -> None:
        n = 30
        errors: list[BaseException] = []
        errors_lock = threading.Lock()

        def place_one() -> None:
            try:
                s = DailyLimitStore(db_path)
                try:
                    s.record_order("AAPL", 100.0)
                finally:
                    s.close()
            except BaseException as e:  # noqa: BLE001 -- capturing for the assertion below
                with errors_lock:
                    errors.append(e)

        threads = [threading.Thread(target=place_one) for _ in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"{len(errors)}/{n} threads raised: {errors}"

        final = DailyLimitStore(db_path)
        try:
            assert final.count_today("AAPL") == n
            assert final.volume_today("AAPL") == 100.0 * n
        finally:
            final.close()
