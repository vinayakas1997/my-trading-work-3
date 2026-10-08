from __future__ import annotations

import pytest

from vinu_live.book.positions import apply_fill, init_book, list_closed_positions, list_open_positions, open_position
from vinu_live.capital_ledger import capital_snapshot, committed_at_cost, trade_results


@pytest.fixture
def book(tmp_path):
    b = init_book(str(tmp_path / "book.db"))
    yield b
    b.close()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("VINU_ACCOUNT_MODE", "VINU_REAL_CAPITAL", "VINU_CAPITAL_RESERVE_FRACTION"):
        monkeypatch.delenv(k, raising=False)


def test_without_a_capital_base_the_snapshot_is_uncapped(book):
    assert capital_snapshot(book)["capped"] is False


def test_committed_money_is_open_positions_at_cost_and_locks_the_cash(book, monkeypatch):
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    apply_fill(book, "AAA", "buy", 2.0, 0.88)          # 1.76 dollars
    snap = capital_snapshot(book)
    assert committed_at_cost(book) == pytest.approx(1.76)
    assert snap["committed"] == pytest.approx(1.76) and snap["reserve"] == pytest.approx(8.0)
    assert snap["free_cash"] == pytest.approx(10.24)


def test_a_closed_trade_releases_the_money_and_shows_in_the_results(book, monkeypatch):
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    apply_fill(book, "AAA", "buy", 2.0, 1.0)
    apply_fill(book, "AAA", "sell", 2.0, 1.1)
    snap = capital_snapshot(book)
    assert snap["committed"] == 0 and snap["free_cash"] == pytest.approx(12.0)
    res = trade_results(book)
    assert res["n_closed"] == 1 and res["n_wins"] == 1 and res["avg_win"] == pytest.approx(0.1)


def test_positions_are_tagged_and_the_other_mode_is_never_counted(book, monkeypatch):
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    open_position(book, "AAA", "long", 10.0, 100.0)
    assert list_open_positions(book)[0].account_mode == "paper"
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    assert list_open_positions(book) == [] and committed_at_cost(book) == 0
    assert capital_snapshot(book)["account_mode"] == "real"
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    assert len(list_open_positions(book)) == 1


def test_closed_trades_of_the_other_mode_are_not_in_the_results(book, monkeypatch):
    apply_fill(book, "AAA", "buy", 1.0, 10.0)
    apply_fill(book, "AAA", "sell", 1.0, 11.0)
    assert len(list_closed_positions(book)) == 1
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    assert list_closed_positions(book) == [] and trade_results(book)["n_closed"] == 0


def test_an_order_still_filling_keeps_its_dollars_locked(book, tmp_path, monkeypatch):
    from vinu_live.execution_log import ExecutionLog

    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    log = ExecutionLog(tmp_path / "e.db")
    log.record(symbol="AAA", side="buy", qty=4, limit_price=1.0, outcome="submitted", order_id="o1")
    snap = capital_snapshot(book, log)
    assert snap["pending_buys"] == pytest.approx(4.0) and snap["free_cash"] == pytest.approx(8.0)
    log.close()
