"""Tests for TickerSnapshotStore -- the dated, per-day record nothing else
in this codebase kept before (TickerSummaryStore overwrites to latest,
TickerLedgerStore is an event log with no as-of query). See
storage/ticker_snapshots.py and the foundation-fixes audit in
missing-pieces-of-system/narating-agents/."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.storage.ticker_snapshots import TickerSnapshotStore


@pytest.fixture
def store() -> TickerSnapshotStore:
    tmp = tempfile.mktemp(suffix=".db")
    s = TickerSnapshotStore(tmp)
    yield s
    s.close()
    Path(tmp).unlink(missing_ok=True)


class TestTickerSnapshotStore:
    def test_record_then_get(self, store: TickerSnapshotStore) -> None:
        store.record_daily_snapshot(
            "AAPL", snapshot_date="2026-09-14", summary="looks constructive",
            angle_digest={"trend_lifecycle": {"stage": "mature"}},
            angles_with_data=1, angle_count=2, source_run_id="run-1",
        )
        fetched = store.get_snapshot("AAPL", "2026-09-14")
        assert fetched is not None
        assert fetched.summary == "looks constructive"
        assert fetched.angle_digest == {"trend_lifecycle": {"stage": "mature"}}
        assert fetched.angles_with_data == 1
        assert fetched.source_run_id == "run-1"

    def test_ticker_normalized_to_uppercase(self, store: TickerSnapshotStore) -> None:
        store.record_daily_snapshot("aapl", snapshot_date="2026-09-14", summary="x")
        assert store.get_snapshot("AAPL", "2026-09-14") is not None
        assert store.get_snapshot("aapl", "2026-09-14") is not None

    def test_get_unknown_returns_none(self, store: TickerSnapshotStore) -> None:
        assert store.get_snapshot("NOPE", "2026-09-14") is None

    def test_same_day_refresh_upserts_not_duplicates(self, store: TickerSnapshotStore) -> None:
        store.record_daily_snapshot("AAPL", snapshot_date="2026-09-14", summary="first")
        store.record_daily_snapshot("AAPL", snapshot_date="2026-09-14", summary="second")
        fetched = store.get_snapshot("AAPL", "2026-09-14")
        assert fetched.summary == "second"
        assert len(store.list_snapshots("AAPL")) == 1

    def test_different_days_produce_separate_rows(self, store: TickerSnapshotStore) -> None:
        store.record_daily_snapshot("AAPL", snapshot_date="2026-09-13", summary="day1")
        store.record_daily_snapshot("AAPL", snapshot_date="2026-09-14", summary="day2")
        rows = store.list_snapshots("AAPL")
        assert len(rows) == 2
        assert {r.snapshot_date for r in rows} == {"2026-09-13", "2026-09-14"}

    def test_created_at_preserved_across_same_day_updates(self, store: TickerSnapshotStore) -> None:
        first = store.record_daily_snapshot("AAPL", snapshot_date="2026-09-14", summary="v1")
        second = store.record_daily_snapshot("AAPL", snapshot_date="2026-09-14", summary="v2")
        assert second.created_at == first.created_at

    def test_no_snapshot_date_defaults_to_today_utc(self, store: TickerSnapshotStore) -> None:
        from datetime import datetime, timezone
        store.record_daily_snapshot("AAPL", summary="today")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert store.get_snapshot("AAPL", today) is not None

    def test_get_latest_before_finds_the_most_recent_prior_day(self, store: TickerSnapshotStore) -> None:
        store.record_daily_snapshot("AAPL", snapshot_date="2026-09-10", summary="old")
        store.record_daily_snapshot("AAPL", snapshot_date="2026-09-12", summary="closer")
        result = store.get_latest_before("AAPL", "2026-09-14")
        assert result is not None
        assert result.snapshot_date == "2026-09-12"
        assert result.summary == "closer"

    def test_get_latest_before_excludes_the_date_itself(self, store: TickerSnapshotStore) -> None:
        store.record_daily_snapshot("AAPL", snapshot_date="2026-09-14", summary="same_day")
        assert store.get_latest_before("AAPL", "2026-09-14") is None

    def test_get_latest_before_no_prior_data_fails_open_to_none(self, store: TickerSnapshotStore) -> None:
        assert store.get_latest_before("AAPL", "2026-09-14") is None

    def test_no_angle_digest_defaults_to_empty_dict(self, store: TickerSnapshotStore) -> None:
        store.record_daily_snapshot("AAPL", snapshot_date="2026-09-14", summary="x")
        fetched = store.get_snapshot("AAPL", "2026-09-14")
        assert fetched.angle_digest == {}
