"""Tests for MarketRegimeHistoryStore -- the durable per-day home for
market_regime_analogue.get_market_regime_stats_for_today()'s output.
See missing-pieces-of-system/maturity-agentic-system/thinking-1/
02-decided-pattern/25-A-Y-details/06-external-signal-cross-check.md ("J").
"""

from __future__ import annotations

import pytest

from vinu_research.storage.market_regime_history import MarketRegimeHistoryStore

_STATS = {
    "n_matches": 5, "n_positive": 4, "n_negative": 1, "positive_ratio": 0.8,
    "avg_return": 0.02, "median_return": 0.015, "max_drawdown": -0.03,
}


class TestMarketRegimeHistoryStore:
    def test_no_rows_returns_empty_history(self, tmp_path):
        store = MarketRegimeHistoryStore(tmp_path / "d.db")
        assert store.all_history() == []

    def test_record_then_read_round_trip(self, tmp_path):
        store = MarketRegimeHistoryStore(tmp_path / "d.db")
        store.record("2026-09-20", _STATS)
        history = store.all_history()
        assert len(history) == 1
        row = history[0]
        assert row["date"] == "2026-09-20"
        assert row["positive_ratio"] == pytest.approx(0.8)
        assert row["n_matches"] == 5

    def test_zero_matches_is_not_recorded(self, tmp_path):
        store = MarketRegimeHistoryStore(tmp_path / "d.db")
        store.record("2026-09-20", {**_STATS, "n_matches": 0})
        assert store.all_history() == []

    def test_empty_stats_is_not_recorded(self, tmp_path):
        store = MarketRegimeHistoryStore(tmp_path / "d.db")
        store.record("2026-09-20", {})
        assert store.all_history() == []

    def test_same_date_recorded_twice_is_not_overwritten(self, tmp_path):
        store = MarketRegimeHistoryStore(tmp_path / "d.db")
        store.record("2026-09-20", _STATS)
        store.record("2026-09-20", {**_STATS, "positive_ratio": 0.1})
        history = store.all_history()
        assert len(history) == 1
        assert history[0]["positive_ratio"] == pytest.approx(0.8)  # first write wins

    def test_all_history_ordered_by_date_ascending(self, tmp_path):
        store = MarketRegimeHistoryStore(tmp_path / "d.db")
        store.record("2026-09-22", _STATS)
        store.record("2026-09-20", _STATS)
        store.record("2026-09-21", _STATS)
        dates = [row["date"] for row in store.all_history()]
        assert dates == ["2026-09-20", "2026-09-21", "2026-09-22"]
