from __future__ import annotations

import pytest

from vinu_research.storage.move_evidence_store import MoveEvidenceStore
from vinu_research.storage.signal_evidence_store import SignalEvidenceStore
from vinu_research.track2_reconciliation import list_unconfirmed_moves


@pytest.fixture
def move_store(tmp_path):
    s = MoveEvidenceStore(tmp_path / "test_move_evidence.db")
    yield s
    s.close()


@pytest.fixture
def signal_store(tmp_path):
    s = SignalEvidenceStore(tmp_path / "test_signal_evidence.db")
    yield s
    s.close()


def _move(move_store, symbol="AAPL", bar_ts=1_700_000_000, window_seconds=900):
    move_store.record_move_event(
        symbol, bar_ts=bar_ts, window_seconds=window_seconds, granularity="15min",
        atr=2.0, price_move=6.0, move_threshold=4.0, direction="up",
    )


def _trigger(signal_store, trigger_id, symbol, trigger_time):
    signal_store.record_trigger(trigger_id, symbol, trigger_time, "sma5_cross_sma50", {})


class TestListUnconfirmedMoves:
    def test_move_with_no_matching_trigger_is_unconfirmed(self, move_store, signal_store):
        _move(move_store)

        result = list_unconfirmed_moves(move_evidence_store=move_store, signal_evidence_store=signal_store)

        assert len(result) == 1
        assert result[0]["confirmed_by_track1"] is False

    def test_move_with_a_matching_trigger_inside_the_window_is_confirmed(self, move_store, signal_store):
        _move(move_store, bar_ts=1_700_000_000, window_seconds=900)
        # trigger_time within 900s of window_time (2023-11-14T22:13:20+00:00)
        _trigger(signal_store, "t1", "AAPL", "2023-11-14T22:13:25+00:00")

        result = list_unconfirmed_moves(move_evidence_store=move_store, signal_evidence_store=signal_store)

        assert result == []

    def test_trigger_outside_the_window_tolerance_still_leaves_it_unconfirmed(self, move_store, signal_store):
        _move(move_store, bar_ts=1_700_000_000, window_seconds=900)
        # trigger_time far outside the 900s tolerance
        _trigger(signal_store, "t1", "AAPL", "2023-11-14T23:59:59+00:00")

        result = list_unconfirmed_moves(move_evidence_store=move_store, signal_evidence_store=signal_store)

        assert len(result) == 1

    def test_trigger_on_a_different_symbol_does_not_confirm(self, move_store, signal_store):
        _move(move_store, symbol="AAPL", bar_ts=1_700_000_000, window_seconds=900)
        _trigger(signal_store, "t1", "MSFT", "2023-11-14T22:13:25+00:00")

        result = list_unconfirmed_moves(move_evidence_store=move_store, signal_evidence_store=signal_store)

        assert len(result) == 1

    def test_symbol_filter_is_forwarded(self, move_store, signal_store):
        _move(move_store, symbol="AAPL")
        _move(move_store, symbol="MSFT")

        result = list_unconfirmed_moves(
            move_evidence_store=move_store, signal_evidence_store=signal_store, symbol="AAPL",
        )

        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL"

    def test_no_moves_on_file_returns_empty(self, move_store, signal_store):
        assert list_unconfirmed_moves(move_evidence_store=move_store, signal_evidence_store=signal_store) == []
