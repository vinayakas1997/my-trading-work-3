"""features-logic-checking D8: the idea generator is shown real moves that no recorded condition fired on."""

from __future__ import annotations

from vinu_research.loop import _build_unconfirmed_moves_context
from vinu_research.storage.move_evidence_store import MoveEvidenceStore
from vinu_research.storage.signal_evidence_store import SignalEvidenceStore

BAR = 1_700_000_000   # any fixed bar time


def _stores(tmp_path):
    return MoveEvidenceStore(tmp_path / "move_evidence.db"), SignalEvidenceStore(tmp_path / "signal_evidence.db")


def _move(moves, symbol, bar_ts, price_move, direction="up", atr=2.0):
    moves.record_move_event(symbol, bar_ts=bar_ts, window_seconds=900, granularity="15min", atr=atr,
                            price_move=price_move, move_threshold=2 * atr, direction=direction)


def test_a_move_nobody_watched_is_described_in_atr(tmp_path):
    moves, signals = _stores(tmp_path)
    _move(moves, "AAPL", BAR, 5.0)                  # ATR 2.0, move 5.0 -> 2.5 ATR
    text = _build_unconfirmed_moves_context("AAPL", tmp_path)
    assert "Recent real moves in AAPL" in text
    assert "up 2.5 ATR on 15min" in text
    assert "not a signal" in text


def test_a_move_a_strategy_condition_did_fire_on_is_left_out(tmp_path):
    moves, signals = _stores(tmp_path)
    _move(moves, "AAPL", BAR, 5.0)
    from datetime import datetime, timezone
    signals.record_trigger("t1", "AAPL", datetime.fromtimestamp(BAR + 60, tz=timezone.utc).isoformat(),
                           "live_indicators.adx_14_gt_20", {"adx_14": 25.0})   # within the 900 s window
    assert _build_unconfirmed_moves_context("AAPL", tmp_path) == ""


def test_other_symbols_and_empty_cases_give_nothing(tmp_path):
    moves, signals = _stores(tmp_path)
    _move(moves, "MSFT", BAR, 5.0)
    assert _build_unconfirmed_moves_context("AAPL", tmp_path) == ""      # other ticker
    assert _build_unconfirmed_moves_context("", tmp_path) == ""          # no symbol
    assert _build_unconfirmed_moves_context("AAPL", None) == ""          # no data root


def test_it_never_creates_a_database_file(tmp_path):
    assert _build_unconfirmed_moves_context("AAPL", tmp_path) == ""
    assert not (tmp_path / "move_evidence.db").exists() and not (tmp_path / "signal_evidence.db").exists()


def test_a_zero_atr_row_says_size_unknown_instead_of_dividing_by_zero(tmp_path):
    moves, _ = _stores(tmp_path)
    _move(moves, "AAPL", BAR, 5.0, atr=0.0)
    assert "size unknown" in _build_unconfirmed_moves_context("AAPL", tmp_path)
