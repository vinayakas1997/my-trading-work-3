"""Tests for AllocationHistoryStore -- vinu-portfolio's first piece of
persistent storage. See storage/allocation_history.py and the
foundation-fixes audit in missing-pieces-of-system/narating-agents/."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_portfolio.storage.allocation_history import AllocationHistoryStore


@pytest.fixture
def store() -> AllocationHistoryStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = AllocationHistoryStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


class TestAllocationHistoryStore:
    def test_record_then_get(self, store: AllocationHistoryStore) -> None:
        store.record_daily_allocation(
            allocation_date="2026-09-14",
            weights=[{"name": "a", "target_weight": 1.0}],
            sleeves={"trending": 1.0}, interval_sleeves={"daily": 1.0},
            account_equity=100_000.0, reserve_fraction=0.3,
            reserve_amount=30_000.0, deployable_equity=70_000.0,
        )
        fetched = store.get_allocation("2026-09-14")
        assert fetched is not None
        assert fetched.weights == [{"name": "a", "target_weight": 1.0}]
        assert fetched.sleeves == {"trending": 1.0}
        assert fetched.account_equity == 100_000.0
        assert fetched.reserve_fraction == 0.3
        assert fetched.deployable_equity == 70_000.0

    def test_get_unknown_returns_none(self, store: AllocationHistoryStore) -> None:
        assert store.get_allocation("2026-09-14") is None

    def test_same_day_call_upserts_not_duplicates(self, store: AllocationHistoryStore) -> None:
        store.record_daily_allocation(allocation_date="2026-09-14", account_equity=100_000.0)
        store.record_daily_allocation(allocation_date="2026-09-14", account_equity=105_000.0)
        fetched = store.get_allocation("2026-09-14")
        assert fetched.account_equity == 105_000.0
        assert len(store.list_allocations()) == 1

    def test_different_days_produce_separate_rows(self, store: AllocationHistoryStore) -> None:
        store.record_daily_allocation(allocation_date="2026-09-13", account_equity=1.0)
        store.record_daily_allocation(allocation_date="2026-09-14", account_equity=2.0)
        rows = store.list_allocations()
        assert len(rows) == 2
        assert {r.allocation_date for r in rows} == {"2026-09-13", "2026-09-14"}

    def test_no_allocation_date_defaults_to_today_utc(self, store: AllocationHistoryStore) -> None:
        from datetime import datetime, timezone
        store.record_daily_allocation(account_equity=1.0)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert store.get_allocation(today) is not None

    def test_get_latest_before_finds_most_recent_prior_day(self, store: AllocationHistoryStore) -> None:
        store.record_daily_allocation(allocation_date="2026-09-10", account_equity=1.0)
        store.record_daily_allocation(allocation_date="2026-09-12", account_equity=2.0)
        result = store.get_latest_before("2026-09-14")
        assert result is not None
        assert result.allocation_date == "2026-09-12"

    def test_get_latest_before_excludes_the_date_itself(self, store: AllocationHistoryStore) -> None:
        store.record_daily_allocation(allocation_date="2026-09-14", account_equity=1.0)
        assert store.get_latest_before("2026-09-14") is None

    def test_no_data_fails_open_to_none(self, store: AllocationHistoryStore) -> None:
        assert store.get_latest_before("2026-09-14") is None

    def test_missing_fields_default_sensibly(self, store: AllocationHistoryStore) -> None:
        store.record_daily_allocation(allocation_date="2026-09-14")
        fetched = store.get_allocation("2026-09-14")
        assert fetched.weights == []
        assert fetched.sleeves == {}
        assert fetched.interval_sleeves == {}
        assert fetched.account_equity is None
        assert fetched.reserve_fraction == 0.0

    def test_created_at_preserved_across_same_day_updates(self, store: AllocationHistoryStore) -> None:
        first = store.record_daily_allocation(allocation_date="2026-09-14", account_equity=1.0)
        second = store.record_daily_allocation(allocation_date="2026-09-14", account_equity=2.0)
        assert second.created_at == first.created_at
