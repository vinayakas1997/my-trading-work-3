from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_screener.audit.watch_history import FiredWatchRecord, WatchAuditStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        s = WatchAuditStore(Path(tmp) / "watch_history.db")
        yield s
        s.close()


class TestRecordAndRead:
    def test_record_fire_is_readable_in_history(self, store: WatchAuditStore) -> None:
        store.record_fire("r1", "AAPL", detail="close > 100", now=100.0)
        history = store.history(rule_id="r1")
        assert len(history) == 1
        assert history[0].symbol == "AAPL"
        assert history[0].detail == "close > 100"

    def test_history_is_most_recent_first(self, store: WatchAuditStore) -> None:
        store.record_fire("r1", "AAPL", now=100.0)
        store.record_fire("r1", "AAPL", now=200.0)
        history = store.history(rule_id="r1")
        assert [h.fired_at for h in history] == [200.0, 100.0]

    def test_record_many_batches_inserts(self, store: WatchAuditStore) -> None:
        records = [
            FiredWatchRecord("r1", "AAPL", 100.0),
            FiredWatchRecord("r1", "MSFT", 100.0),
        ]
        store.record_many(records)
        assert store.count(rule_id="r1") == 2


class TestFiltering:
    def test_filters_by_symbol(self, store: WatchAuditStore) -> None:
        store.record_fire("r1", "AAPL", now=1.0)
        store.record_fire("r1", "MSFT", now=2.0)
        history = store.history(symbol="AAPL")
        assert [h.symbol for h in history] == ["AAPL"]

    def test_filters_by_since(self, store: WatchAuditStore) -> None:
        store.record_fire("r1", "AAPL", now=100.0)
        store.record_fire("r1", "AAPL", now=200.0)
        history = store.history(since=150.0)
        assert len(history) == 1
        assert history[0].fired_at == 200.0

    def test_limit_caps_results(self, store: WatchAuditStore) -> None:
        for i in range(5):
            store.record_fire("r1", "AAPL", now=float(i))
        history = store.history(rule_id="r1", limit=2)
        assert len(history) == 2


class TestPermanence:
    def test_history_survives_regardless_of_live_state(self, store: WatchAuditStore) -> None:
        # This module doesn't know about CooldownGate at all -- a fire is
        # written once and stays, independent of any live rule reset.
        store.record_fire("r1", "AAPL", now=1.0)
        # Nothing here can "reset" a fired_watches row; only a fresh
        # record_fire adds one. Confirm count is stable across reads.
        assert store.count(rule_id="r1") == 1
        assert store.count(rule_id="r1") == 1

    def test_empty_history_for_unknown_rule(self, store: WatchAuditStore) -> None:
        assert store.history(rule_id="ghost") == []
        assert store.count(rule_id="ghost") == 0
