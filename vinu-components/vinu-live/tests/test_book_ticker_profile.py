"""Tests for book/positions.py's shared ticker-profile write -- best-
effort, resolved from VINU_SHARED_ROOT, ships inert when unset."""

import os
import tempfile

import pytest

from vinu_infra.ticker_profile import read_ticker_profile
from vinu_live.book import close_position, init_book, open_position, reduce_position


@pytest.fixture
def book():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    be = init_book(db_path)
    yield be
    be.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


class TestShipsInert:
    def test_open_position_writes_nothing_when_shared_root_unset(self, book, monkeypatch, tmp_path) -> None:
        monkeypatch.delenv("VINU_SHARED_ROOT", raising=False)
        open_position(book, "AAPL", "buy", 100, 150.0)
        assert not (tmp_path / "ticker-profiles").exists()


class TestWritesWhenSharedRootSet:
    def test_open_position_writes_profile(self, book, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("VINU_SHARED_ROOT", str(tmp_path))
        pos = open_position(book, "AAPL", "buy", 100, 150.0)

        profile = read_ticker_profile(tmp_path, "AAPL")["vinu_live"]
        assert profile["side"] == "long"
        assert profile["qty"] == 100
        assert profile["avg_entry"] == 150.0
        assert profile["is_open"] is True
        assert profile["position_id"] == pos.position_id

    def test_close_position_writes_closed_state_with_realized_pnl(self, book, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("VINU_SHARED_ROOT", str(tmp_path))
        pos = open_position(book, "MSFT", "buy", 10, 100.0)
        close_position(book, pos.position_id, 110.0)

        profile = read_ticker_profile(tmp_path, "MSFT")["vinu_live"]
        assert profile["is_open"] is False
        assert profile["realized_pnl"] == pytest.approx(100.0)

    def test_full_reduce_to_zero_writes_closed_state(self, book, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("VINU_SHARED_ROOT", str(tmp_path))
        pos = open_position(book, "GOOG", "buy", 10, 100.0)
        reduce_position(book, pos.position_id, 10, 105.0)

        profile = read_ticker_profile(tmp_path, "GOOG")["vinu_live"]
        assert profile["is_open"] is False
        assert profile["realized_pnl"] == pytest.approx(50.0)

    def test_partial_reduce_stays_open_and_updates_qty(self, book, monkeypatch, tmp_path) -> None:
        monkeypatch.setenv("VINU_SHARED_ROOT", str(tmp_path))
        pos = open_position(book, "TSLA", "buy", 10, 100.0)
        reduce_position(book, pos.position_id, 4, 105.0)

        profile = read_ticker_profile(tmp_path, "TSLA")["vinu_live"]
        assert profile["is_open"] is True
        assert profile["qty"] == 6
