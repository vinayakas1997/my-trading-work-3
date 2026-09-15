"""Tests for CorrelationMonitorStore -- per-cycle history of
_check_runtime_correlation's own output, previously recomputed and
returned once per cycle then dropped. See
trade_plan/correlation_monitor_store.py and the foundation-fixes audit in
missing-pieces-of-system/narating-agents/."""

from __future__ import annotations

from vinu_live.trade_plan.correlation_monitor_store import CorrelationMonitorStore


class TestCorrelationMonitorStore:
    def test_record_then_list(self) -> None:
        store = CorrelationMonitorStore(":memory:")
        store.record_cycle(1, [{"pair": ["AAA", "BBB"], "correlation": 0.95}], [])
        rows = store.list_recent()
        assert len(rows) == 1
        assert rows[0].n_flagged == 1
        assert rows[0].flagged == [{"pair": ["AAA", "BBB"], "correlation": 0.95}]
        assert rows[0].reductions == []
        store.close()

    def test_empty_store_returns_empty_list(self) -> None:
        store = CorrelationMonitorStore(":memory:")
        assert store.list_recent() == []
        store.close()

    def test_most_recent_first(self) -> None:
        store = CorrelationMonitorStore(":memory:")
        store.record_cycle(0, [], [])
        store.record_cycle(1, [{"pair": ["AAA", "BBB"]}], [])
        rows = store.list_recent()
        assert rows[0].n_flagged == 1
        assert rows[1].n_flagged == 0
        store.close()

    def test_limit_is_respected(self) -> None:
        store = CorrelationMonitorStore(":memory:")
        for i in range(5):
            store.record_cycle(i, [], [])
        rows = store.list_recent(limit=2)
        assert len(rows) == 2
        assert rows[0].n_flagged == 4
        store.close()

    def test_multiple_cycles_each_get_their_own_row(self) -> None:
        store = CorrelationMonitorStore(":memory:")
        store.record_cycle(1, [{"pair": ["A", "B"]}], [])
        store.record_cycle(2, [{"pair": ["A", "C"]}], [{"symbol": "A"}])
        rows = store.list_recent()
        assert len(rows) == 2
        store.close()
