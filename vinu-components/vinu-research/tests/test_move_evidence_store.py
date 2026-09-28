from __future__ import annotations

import pytest

from vinu_research.storage.move_evidence_store import MoveEvidenceStore


@pytest.fixture
def store(tmp_path):
    s = MoveEvidenceStore(tmp_path / "test_move_evidence.db")
    yield s
    s.close()


class TestRecordMoveEvent:
    def test_records_and_lists_back(self, store):
        event_id = store.record_move_event(
            "AAPL", bar_ts=1_700_000_000, window_seconds=900, granularity="15min",
            atr=2.0, price_move=6.0, move_threshold=4.0, direction="up",
        )
        assert isinstance(event_id, int)

        events = store.list_move_events(symbol="AAPL")
        assert len(events) == 1
        assert events[0]["symbol"] == "AAPL"
        assert events[0]["atr"] == 2.0
        assert events[0]["direction"] == "up"
        assert events[0]["window_time"] is not None

    def test_window_time_is_derived_from_bar_ts(self, store):
        store.record_move_event(
            "AAPL", bar_ts=1_700_000_000, window_seconds=900, granularity="15min",
            atr=2.0, price_move=6.0, move_threshold=4.0, direction="up",
        )
        events = store.list_move_events(symbol="AAPL")
        assert events[0]["window_time"] == "2023-11-14T22:13:20+00:00"

    def test_list_filters_by_symbol(self, store):
        store.record_move_event(
            "AAPL", bar_ts=1_700_000_000, window_seconds=900, granularity="15min",
            atr=2.0, price_move=6.0, move_threshold=4.0, direction="up",
        )
        store.record_move_event(
            "MSFT", bar_ts=1_700_000_100, window_seconds=900, granularity="15min",
            atr=1.0, price_move=-3.0, move_threshold=2.0, direction="down",
        )
        events = store.list_move_events(symbol="AAPL")
        assert len(events) == 1
        assert events[0]["symbol"] == "AAPL"

    def test_list_orders_most_recent_first(self, store):
        store.record_move_event(
            "AAPL", bar_ts=1_700_000_000, window_seconds=900, granularity="15min",
            atr=2.0, price_move=6.0, move_threshold=4.0, direction="up",
        )
        store.record_move_event(
            "AAPL", bar_ts=1_700_001_000, window_seconds=900, granularity="15min",
            atr=2.0, price_move=6.0, move_threshold=4.0, direction="up",
        )
        events = store.list_move_events(symbol="AAPL")
        assert events[0]["bar_ts"] == 1_700_001_000
        assert events[1]["bar_ts"] == 1_700_000_000

    def test_no_events_on_file_returns_empty_list(self, store):
        assert store.list_move_events(symbol="AAPL") == []
