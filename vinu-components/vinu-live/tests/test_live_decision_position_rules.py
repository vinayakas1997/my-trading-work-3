"""logic-audit-2026-10-02 A3 (the-inconsistencies-v2, plan item 2.3): rule-based
stop / max-hold for a live-decision position.

Layers: the pure rule function; the new `entry_price` column (migration of an
old database, write-once setter); the scheduler stamping the entry price; the
poller closing a position on a breach, both directly and through a full
`cycle()`; and the guarantee that nothing changes for a strategy that sets
neither field.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from vinu_live.config import LiveConfig
from vinu_live.live_decision.poller import CandleClosePoller
from vinu_live.live_decision.position_rules import evaluate_position_rules
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    list_live_decisions,
    list_open_positions,
    open_position,
    set_entry_price_if_missing,
)
from vinu_live.scheduler import LiveScheduler

TF = 900  # 15m


def _rule(**over):
    base = dict(
        position_size=0.05, entry_price=100.0, last_close=100.0,
        opened_bar_ts=1_000_000, bar_ts=1_000_000 + TF, timeframe_seconds=TF,
        stop_pct=0.0, max_hold_bars=0,
    )
    base.update(over)
    return evaluate_position_rules(**base)


# ------------------------------------------------------------------ pure rules

def test_both_rules_off_never_exit():
    assert _rule(last_close=1.0, bar_ts=10**9) is None


def test_long_stop_triggers_at_and_below_the_level_only():
    assert _rule(stop_pct=0.05, last_close=95.01) is None
    assert _rule(stop_pct=0.05, last_close=95.0)[0] == "stop_loss"
    assert _rule(stop_pct=0.05, last_close=80.0)[0] == "stop_loss"


def test_short_stop_triggers_on_a_rise_not_a_fall():
    assert _rule(position_size=-0.05, stop_pct=0.05, last_close=90.0) is None
    assert _rule(position_size=-0.05, stop_pct=0.05, last_close=105.0)[0] == "stop_loss"


def test_stop_needs_an_entry_price_and_is_skipped_without_one():
    assert _rule(stop_pct=0.05, entry_price=None, last_close=1.0) is None
    assert _rule(stop_pct=0.05, entry_price=0.0, last_close=1.0) is None
    assert _rule(stop_pct=0.05, entry_price=float("nan"), last_close=1.0) is None


def test_a_bad_current_price_never_triggers_a_stop():
    assert _rule(stop_pct=0.05, last_close=0.0) is None
    assert _rule(stop_pct=0.05, last_close=float("nan")) is None


def test_max_hold_counts_elapsed_bars():
    opened = 1_000_000
    assert _rule(max_hold_bars=10, opened_bar_ts=opened, bar_ts=opened + 9 * TF) is None
    hit = _rule(max_hold_bars=10, opened_bar_ts=opened, bar_ts=opened + 10 * TF)
    assert hit is not None and hit[0] == "max_hold" and "10 bars" in hit[1]


def test_max_hold_works_without_any_price():
    hit = _rule(max_hold_bars=1, entry_price=None, last_close=float("nan"), bar_ts=1_000_000 + 2 * TF)
    assert hit is not None and hit[0] == "max_hold"


def test_stop_is_reported_before_max_hold_when_both_breach():
    hit = _rule(stop_pct=0.05, last_close=90.0, max_hold_bars=1, bar_ts=1_000_000 + 5 * TF)
    assert hit[0] == "stop_loss"


# ------------------------------------------------------------------ storage

@pytest.fixture
def backend():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    b = LiveDecisionBackend(path)
    yield b
    b.close()
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.unlink(path + suffix)


def _open(backend, ticker="AAPL", strategy="s1", size=0.05, opened=1_000_000):
    return open_position(
        backend, ticker=ticker, strategy_id=strategy, position_size=size,
        opened_bar_ts=opened, trigger_id="t1",
    )


def test_new_position_has_no_entry_price_until_stamped(backend):
    pos = _open(backend)
    assert pos.entry_price is None
    assert list_open_positions(backend)[0].entry_price is None


def test_entry_price_is_write_once(backend):
    pos = _open(backend)
    assert set_entry_price_if_missing(backend, pos.id, 101.5) is True
    assert set_entry_price_if_missing(backend, pos.id, 140.0) is False  # never overwritten
    assert list_open_positions(backend)[0].entry_price == 101.5


@pytest.mark.parametrize("bad", [0.0, -5.0, None])
def test_entry_price_rejects_unusable_values(backend, bad):
    pos = _open(backend)
    assert set_entry_price_if_missing(backend, pos.id, bad) is False
    assert list_open_positions(backend)[0].entry_price is None


def test_an_old_database_without_the_column_is_migrated_and_stays_readable(tmp_path):
    db = tmp_path / "old_live_decision.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE live_decision_open_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL, strategy_id TEXT NOT NULL,
            position_size REAL NOT NULL, opened_bar_ts INTEGER NOT NULL, trigger_id TEXT,
            status TEXT NOT NULL DEFAULT 'open', opened_at TEXT NOT NULL,
            last_reviewed_bar_ts INTEGER, closed_at TEXT, closed_bar_ts INTEGER, closed_reason TEXT
        );
        INSERT INTO live_decision_open_positions
            (ticker, strategy_id, position_size, opened_bar_ts, status, opened_at)
            VALUES ('MSFT', 'old', 0.02, 5, 'open', '2026-09-01T00:00:00+00:00');
        PRAGMA user_version=4;
        """
    )
    con.commit()
    con.close()

    b = LiveDecisionBackend(str(db))
    try:
        rows = list_open_positions(b)
        assert len(rows) == 1 and rows[0].ticker == "MSFT" and rows[0].entry_price is None
        assert set_entry_price_if_missing(b, rows[0].id, 300.0) is True
    finally:
        b.close()


# ------------------------------------------------------------------ scheduler stamping

def _scheduler(tmp_path) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(data_root=tmp_path))
    s._http = MagicMock()
    return s


def test_scheduler_stamps_the_first_priced_cycle_and_never_restamps(tmp_path):
    s = _scheduler(tmp_path)
    p1 = _open(s._live_decision_backend, "AAPL")
    p2 = _open(s._live_decision_backend, "NVDA", strategy="s2")
    s._record_live_decision_entry_prices({"AAPL": 150.0})  # NVDA not priced this cycle
    by_ticker = {p.ticker: p for p in list_open_positions(s._live_decision_backend)}
    assert by_ticker["AAPL"].entry_price == 150.0 and by_ticker["NVDA"].entry_price is None
    s._record_live_decision_entry_prices({"AAPL": 999.0, "NVDA": 400.0})
    by_ticker = {p.ticker: p for p in list_open_positions(s._live_decision_backend)}
    assert by_ticker["AAPL"].entry_price == 150.0 and by_ticker["NVDA"].entry_price == 400.0
    assert p1.id != p2.id


def test_scheduler_stamping_never_raises_into_order_flow(tmp_path):
    s = _scheduler(tmp_path)
    s._live_decision_backend = MagicMock()
    s._live_decision_backend._get_conn.side_effect = RuntimeError("db gone")
    s._record_live_decision_entry_prices({"AAPL": 150.0})  # must not raise


# ------------------------------------------------------------------ poller

@pytest.fixture
def poller():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    b = LiveDecisionBackend(path)
    p = CandleClosePoller(LiveConfig(), backend=b)
    p._http = MagicMock()
    yield p
    b.close()
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.unlink(path + suffix)


def _bars_df(close: float) -> pd.DataFrame:
    return pd.DataFrame({"close": [close - 1.0, close], "bar_ts": [1_000_000, 1_000_000 + TF]})


def _strat(**extra):
    return {"name": "s1", "schedule": "15m", "universe": ["AAPL"], **extra}


def test_poller_closes_a_position_on_a_stop_and_records_an_exit(poller):
    pos = _open(poller._backend)
    set_entry_price_if_missing(poller._backend, pos.id, 100.0)
    closed = poller._apply_position_rules(
        "AAPL", "15m", 1_000_000 + TF, _bars_df(94.0), [_strat(live_decision_stop_pct=0.05)],
    )
    assert closed == 1
    assert list_open_positions(poller._backend) == []
    done = list_open_positions(poller._backend, status="closed")[0]
    assert done.closed_reason.startswith("rule_exit:stop_loss")
    rec = list_live_decisions(poller._backend, ticker="AAPL")[0]
    assert rec.decision == "EXIT" and rec.trigger_id == f"pos_{pos.id}" and "stop" in rec.reasoning


def test_poller_closes_on_max_hold_even_without_an_entry_price(poller):
    _open(poller._backend, opened=1_000_000 - 20 * TF)
    closed = poller._apply_position_rules(
        "AAPL", "15m", 1_000_000 + TF, _bars_df(100.0), [_strat(live_decision_max_hold_bars=10)],
    )
    assert closed == 1
    assert "max_hold" in list_open_positions(poller._backend, status="closed")[0].closed_reason


def test_poller_does_nothing_when_neither_field_is_set(poller):
    pos = _open(poller._backend, opened=1)
    set_entry_price_if_missing(poller._backend, pos.id, 100.0)
    assert poller._apply_position_rules("AAPL", "15m", 10**9, _bars_df(1.0), [_strat()]) == 0
    assert len(list_open_positions(poller._backend)) == 1


def test_poller_ignores_other_tickers_and_other_strategies(poller):
    other_t = _open(poller._backend, ticker="MSFT")
    other_s = _open(poller._backend, ticker="AAPL", strategy="unwatched")
    for p in (other_t, other_s):
        set_entry_price_if_missing(poller._backend, p.id, 100.0)
    closed = poller._apply_position_rules(
        "AAPL", "15m", 1_000_000 + TF, _bars_df(10.0), [_strat(live_decision_stop_pct=0.05)],
    )
    assert closed == 0 and len(list_open_positions(poller._backend)) == 2


def test_poller_never_raises_on_empty_or_malformed_bars(poller):
    pos = _open(poller._backend)
    set_entry_price_if_missing(poller._backend, pos.id, 100.0)
    strat = [_strat(live_decision_stop_pct=0.05)]
    assert poller._apply_position_rules("AAPL", "15m", 1, pd.DataFrame(), strat) == 0
    assert poller._apply_position_rules("AAPL", "15m", 1, pd.DataFrame({"x": [1]}), strat) == 0
    assert poller._apply_position_rules("AAPL", "15m", 1, None, strat) == 0
    assert len(list_open_positions(poller._backend)) == 1


def _resp(json_body):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = json_body
    r.raise_for_status = MagicMock()
    return r


def test_full_cycle_closes_the_position_through_the_real_loop(poller):
    """End to end through CandleClosePoller.cycle(): strategy config carries
    max_hold_bars, a fresh candle arrives, the position opened long ago is
    closed -- no agent call is made for it."""
    start = 1_700_000_000
    rows = [
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5 + i, "volume": 1000.0, "ts": start + i * TF}
        for i in range(260)
    ]
    _open(poller._backend, opened=start)  # opened 259 bars before the newest candle

    async def _get(url, params=None, **kwargs):
        if "/strategy/strategies/s1" in url:
            return _resp({
                "name": "s1", "schedule": "15m", "universe": ["AAPL"],
                "must_conditions": [], "confirmation_conditions": [], "grace_window_bars": 5,
                "live_decision_max_hold_bars": 50,
            })
        if "/strategy/strategies" in url:
            return _resp([{"name": "s1", "enabled": True}])
        if "/stock/candles/AAPL" in url:
            limit = (params or {}).get("limit", 2)
            return _resp({"data": rows[-min(limit, 260):]})
        raise AssertionError(f"unexpected URL: {url}")

    poller._http.get = AsyncMock(side_effect=_get)
    poller._http.post = AsyncMock(side_effect=AssertionError("no agent/HTTP POST expected for a rule exit"))

    asyncio.run(poller.cycle())

    assert list_open_positions(poller._backend) == []
    assert "max_hold" in list_open_positions(poller._backend, status="closed")[0].closed_reason
