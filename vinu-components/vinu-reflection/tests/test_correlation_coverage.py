"""Tests for analysis E, pair piece (cross-package systemic risk via
pairwise correlation)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vinu_live.book.positions import BookBackend
from vinu_live.trade_plan.correlation_monitor_store import CorrelationMonitorStore

from vinu_reflection.reflection import correlation_coverage


@pytest.fixture
def data_root(tmp_path) -> Path:
    return tmp_path


def _open_position(book: BookBackend, symbol: str) -> None:
    conn = book._get_conn()
    conn.execute(
        "INSERT INTO open_positions "
        "(position_id, symbol, side, qty, avg_entry, opened_at, updated_at) "
        "VALUES (?, ?, 'long', 10, 100.0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
        (f"pos_{symbol}", symbol),
    )
    conn.commit()


def _record_cycle(store: CorrelationMonitorStore, flagged_pairs: list[tuple[str, str, float]]) -> None:
    flagged = [{"pair": [a, b], "correlation": corr} for a, b, corr in flagged_pairs]
    store.record_cycle(len(flagged), flagged, [])


class TestCorrelationCoverageRun:
    def test_fewer_than_two_positions_returns_no_findings(self, data_root):
        book = BookBackend(str(data_root / "trade_plan_book.db"))
        _open_position(book, "AAPL")
        CorrelationMonitorStore(str(data_root / "correlation_monitor.db"))
        assert correlation_coverage.run({"vinu_live": data_root}) == []

    def test_no_flagged_history_returns_no_findings(self, data_root):
        book = BookBackend(str(data_root / "trade_plan_book.db"))
        _open_position(book, "AAPL")
        _open_position(book, "MSFT")
        CorrelationMonitorStore(str(data_root / "correlation_monitor.db"))
        assert correlation_coverage.run({"vinu_live": data_root}) == []

    def test_climbing_correlation_for_held_pair_is_flagged(self, data_root):
        book = BookBackend(str(data_root / "trade_plan_book.db"))
        _open_position(book, "AAPL")
        _open_position(book, "MSFT")
        corr_store = CorrelationMonitorStore(str(data_root / "correlation_monitor.db"))

        # 8 reference cycles, low correlation.
        for _ in range(8):
            _record_cycle(corr_store, [("AAPL", "MSFT", 0.2)])
        # 3 recent cycles, much higher correlation.
        for _ in range(3):
            _record_cycle(corr_store, [("AAPL", "MSFT", 0.9)])

        findings = correlation_coverage.run({"vinu_live": data_root})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.scope_type == "ticker_pair"
        assert finding.scope_key == "AAPL|MSFT"
        assert finding.metric_name == "correlation_trend"
        assert finding.primary_metric == pytest.approx(0.7, abs=1e-6)
        assert finding.psi > 0.25
        assert finding.evidence_count == 11
        assert finding.signal_json["weeks_climbing"] == 3

    def test_pair_not_currently_held_is_ignored(self, data_root):
        book = BookBackend(str(data_root / "trade_plan_book.db"))
        _open_position(book, "AAPL")  # only one position open -- pair not held
        corr_store = CorrelationMonitorStore(str(data_root / "correlation_monitor.db"))
        for _ in range(11):
            _record_cycle(corr_store, [("AAPL", "MSFT", 0.9)])

        assert correlation_coverage.run({"vinu_live": data_root}) == []

    def test_below_evidence_minimum_is_skipped(self, data_root):
        book = BookBackend(str(data_root / "trade_plan_book.db"))
        _open_position(book, "AAPL")
        _open_position(book, "MSFT")
        corr_store = CorrelationMonitorStore(str(data_root / "correlation_monitor.db"))
        for _ in range(5):
            _record_cycle(corr_store, [("AAPL", "MSFT", 0.9)])

        assert correlation_coverage.run({"vinu_live": data_root}) == []
