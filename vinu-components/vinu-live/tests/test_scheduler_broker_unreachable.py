"""Loud failure reporting when the broker (Alpaca, reached through the agent API) cannot be read.

Before: an unreadable positions list aborted the cycle with one log line; an unreadable equity fell back silently
(or aborted, with the A7 flag); a failing order submission was one warning. Nothing told a human. Now: an ERROR log,
a `broker_unreachable` list in the cycle result, one CRITICAL notification on the first bad cycle, a reminder every N
consecutive bad cycles, and one "recovered" message. Notification only: it never changes what the scheduler does.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_live.config import LiveConfig
from vinu_live.scheduler import LiveScheduler


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = RuntimeError(f"HTTP {status}")
    return r


class _World:
    """Switchable fake: broker reads / order posts can be made to fail."""
    def __init__(self):
        self.positions_ok = True
        self.account = "ok"          # ok | error | unconfigured | down
        self.orders = "ok"           # ok | http500 | raise
        self.notices: list[dict] = []

    async def get(self, url, params=None, **kw):
        if "/portfolio/state" in url:
            return _resp(200, {"weights": [{"symbol": "AAPL", "target_weight": 0.1}]})
        if "/broker/positions" in url:
            return _resp(200, []) if self.positions_ok else _resp(503)
        if "/broker/account" in url:
            if self.account == "down":
                raise ConnectionError("agent api down")
            if self.account == "unconfigured":
                return _resp(200, {"configured": False})
            if self.account == "error":
                return _resp(200, {"configured": True, "equity": None, "error": "alpaca timeout"})
            return _resp(200, {"configured": True, "equity": 100_000.0})
        if "/candles/" in url:
            return _resp(200, {"data": [{"close": 100.0, "bar_ts": 1_700_000_000}]})
        return _resp(404)

    async def post(self, url, json=None, **kw):
        if "/notify/reconciliation-drift" in url:
            self.notices.append(json)
            return _resp(200, {"delivered": 1})
        if "/broker/order" in url:
            if self.orders == "raise":
                raise ConnectionError("connection reset")
            if self.orders == "http500":
                return _resp(500)
            return _resp(200, {"status": "submitted", "order_id": "o1"})
        return _resp(200)


def _sched(tmp_path, world, **cfg) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(data_root=tmp_path, twap_slices=1, **cfg))
    s._http = MagicMock()
    s._http.get = AsyncMock(side_effect=world.get)
    s._http.post = AsyncMock(side_effect=world.post)
    s._check_breaker = AsyncMock(return_value=("ALLOW", None))
    return s


def _cycle(s):
    with patch("vinu_live.scheduler.asyncio.sleep", AsyncMock()), patch("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None)):
        return asyncio.run(s.cycle())


def test_flags_default_on_and_read_env(monkeypatch):
    c = LiveConfig()
    assert c.broker_unreachable_notify_enabled is True and c.broker_unreachable_renotify_cycles == 6
    monkeypatch.setenv("VINU_LIVE_BROKER_UNREACHABLE_NOTIFY_ENABLED", "false")
    monkeypatch.setenv("VINU_LIVE_BROKER_UNREACHABLE_RENOTIFY_CYCLES", "3")
    c = LiveConfig.from_env()
    assert c.broker_unreachable_notify_enabled is False and c.broker_unreachable_renotify_cycles == 3


def test_a_healthy_cycle_says_nothing(tmp_path):
    w = _World()
    r = _cycle(_sched(tmp_path, w))
    assert r["status"] == "ok" and "broker_unreachable" not in r and w.notices == []


def test_unreadable_positions_is_reported_loudly_and_the_cycle_still_fails_as_before(tmp_path):
    w = _World()
    w.positions_ok = False
    r = _cycle(_sched(tmp_path, w))
    assert r["status"] == "failed"
    assert r["broker_unreachable"] and "positions could not be read" in r["broker_unreachable"][0]
    (n,) = w.notices
    assert n["symbol"] == "BROKER" and n["action"] == "broker_unreachable" and "positions could not be read" in n["detail"]


def test_unreadable_equity_of_a_configured_broker_is_reported_even_with_the_abort_flag_off(tmp_path):
    w = _World()
    w.account = "error"
    r = _cycle(_sched(tmp_path, w, abort_on_equity_read_failure=False))
    assert r["status"] == "ok"                                          # behavior unchanged: it still traded
    assert any("equity could not be read" in p for p in r["broker_unreachable"])
    assert len(w.notices) == 1


def test_an_unconfigured_broker_is_not_an_outage(tmp_path):
    w = _World()
    w.account = "unconfigured"
    r = _cycle(_sched(tmp_path, w))
    assert "broker_unreachable" not in r and w.notices == []


@pytest.mark.parametrize("orders", ["http500", "raise"])
def test_failing_order_submissions_are_reported(tmp_path, orders):
    w = _World()
    w.orders = orders
    r = _cycle(_sched(tmp_path, w))
    assert any("order for AAPL" in p for p in r["broker_unreachable"])
    assert len(w.notices) == 1


def test_a_refused_order_is_not_a_broker_outage(tmp_path):
    """A rejection is the safety layer working, not the broker being unreachable."""
    w = _World()
    original = w.post

    async def post(url, json=None, **kw):
        if "/broker/order" in url:
            return _resp(200, {"status": "rejected", "reason": "kill switch"})
        return await original(url, json=json, **kw)

    s = _sched(tmp_path, w)
    s._http.post = AsyncMock(side_effect=post)
    r = _cycle(s)
    assert "broker_unreachable" not in r and w.notices == []


def test_the_notification_is_edge_triggered_reminds_every_n_and_announces_recovery(tmp_path):
    w = _World()
    s = _sched(tmp_path, w, broker_unreachable_renotify_cycles=3)
    w.positions_ok = False
    for _ in range(7):
        _cycle(s)
    actions = [n["action"] for n in w.notices]
    assert actions == ["broker_unreachable", "broker_unreachable", "broker_unreachable"]      # cycles 1, 3, 6
    assert "1 consecutive" in w.notices[0]["detail"] and "3 consecutive" in w.notices[1]["detail"]
    w.positions_ok = True
    r = _cycle(s)
    assert "broker_unreachable" not in r
    assert w.notices[-1]["action"] == "broker_recovered" and "7 bad cycle" in w.notices[-1]["detail"]
    _cycle(s)
    assert [n["action"] for n in w.notices].count("broker_recovered") == 1               # said once


def test_disabled_logs_and_reports_in_the_result_but_sends_nothing(tmp_path):
    w = _World()
    w.positions_ok = False
    r = _cycle(_sched(tmp_path, w, broker_unreachable_notify_enabled=False))
    assert r["broker_unreachable"] and w.notices == []


def test_a_failing_notification_never_breaks_the_cycle(tmp_path):
    w = _World()
    w.positions_ok = False
    s = _sched(tmp_path, w)
    original = w.post

    async def post(url, json=None, **kw):
        if "/notify/" in url:
            raise ConnectionError("notify down")
        return await original(url, json=json, **kw)

    s._http.post = AsyncMock(side_effect=post)
    r = _cycle(s)
    assert r["status"] == "failed" and r["broker_unreachable"]


def test_the_problem_list_does_not_leak_into_the_next_cycle(tmp_path):
    w = _World()
    s = _sched(tmp_path, w)
    w.account = "error"
    _cycle(s)
    w.account = "ok"
    assert "broker_unreachable" not in _cycle(s)


def test_a_cycle_that_never_reached_the_broker_changes_nothing(tmp_path):
    """No target weights -> the cycle skips before any broker read; the streak must be left alone, not reset."""
    w = _World()
    s = _sched(tmp_path, w)
    w.positions_ok = False
    _cycle(s)
    assert s._broker_down_streak == 1

    async def empty_state(url, params=None, **kw):
        if "/portfolio/state" in url:
            return _resp(200, {"status": "empty", "weights": []})
        return await w.get(url, params, **kw)

    s._http.get = AsyncMock(side_effect=empty_state)
    r = _cycle(s)
    assert r["status"] == "skipped_no_weights" and s._broker_down_streak == 1 and len(w.notices) == 1
