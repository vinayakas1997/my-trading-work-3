from __future__ import annotations

import pytest

from vinu_live.book.positions import apply_fill, init_book, list_open_positions
from vinu_live.book.sync import sync_book_to_broker
from vinu_live.capital_ledger import capital_snapshot, trade_results


@pytest.fixture
def book(tmp_path, monkeypatch):
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    b = init_book(str(tmp_path / "book.db"))
    yield b
    b.close()


def test_a_position_the_broker_no_longer_holds_is_closed_in_the_book_and_frees_the_money(book):
    apply_fill(book, "AAA", "buy", 2.0, 0.88)
    assert capital_snapshot(book)["free_cash"] == pytest.approx(10.24)
    out = sync_book_to_broker(book, {})
    assert out and out[0]["cut_qty"] == 2.0 and list_open_positions(book) == []
    assert capital_snapshot(book)["free_cash"] == pytest.approx(12.0)


def test_a_partly_sold_position_is_cut_to_the_brokers_quantity(book):
    apply_fill(book, "AAA", "buy", 5.0, 1.0)
    sync_book_to_broker(book, {"AAA": 3.0})
    assert list_open_positions(book)[0].qty == pytest.approx(3.0)


def test_the_book_is_never_grown_to_match_a_larger_broker_position(book):
    apply_fill(book, "AAA", "buy", 2.0, 1.0)
    assert sync_book_to_broker(book, {"AAA": 10.0}) == []
    assert list_open_positions(book)[0].qty == 2.0


def test_a_cut_with_no_known_exit_price_is_not_counted_as_a_win_or_a_loss(book):
    apply_fill(book, "AAA", "buy", 2.0, 1.0)
    sync_book_to_broker(book, {})
    assert trade_results(book)["n_closed"] == 0


def test_the_scheduler_syncs_the_book_even_in_a_cycle_with_nothing_to_trade(tmp_path, monkeypatch):
    """Found in the live drill: the manual exit left AAPL in the book and every cycle returned before reaching the sync."""
    import asyncio
    from tests.test_scheduler_allocation_and_ownership import _router, _run, _sched

    s = _sched(tmp_path, twap_slices=1, scheduler_respect_trade_plan_symbols=True)
    apply_fill(s._book, "OLD", "buy", 2.0, 1.0)
    s._http.get = _router(state={"status": "empty", "weights": []}, positions=[], plans=[])
    r = _run(s, monkeypatch)
    assert r["status"] == "skipped_no_weights" and r["book_synced"][0]["symbol"] == "OLD"
    assert list_open_positions(s._book) == []
