"""logic-audit-2026-10-02 A7 (the-inconsistencies-v2, Phase 4): a failed read of a CONFIGURED
broker's equity must abort the scheduler cycle, not size orders on a placeholder.

Opt-in (`abort_on_equity_read_failure`, default off). `configured: false` (no broker at all)
still legitimately uses the placeholder.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.config import LiveConfig
from vinu_live.scheduler import LiveScheduler


def _sched(abort: bool, **cfg) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(abort_on_equity_read_failure=abort, **cfg))
    s._http = MagicMock()
    return s


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


def _value(s: LiveScheduler, positions=None, prices=None):
    return asyncio.run(s._fetch_portfolio_value(positions or {}, prices or {}))


def test_flag_defaults_off():
    assert LiveConfig().abort_on_equity_read_failure is False


def test_from_env_reads_the_flag(monkeypatch):
    monkeypatch.setenv("VINU_LIVE_ABORT_ON_EQUITY_READ_FAILURE", "true")
    assert LiveConfig.from_env().abort_on_equity_read_failure is True


@pytest.mark.parametrize("failure", ["exception", "http500", "no_equity", "bad_shape"])
def test_failed_read_of_a_configured_broker_aborts_when_on(failure):
    s = _sched(True)
    if failure == "exception":
        s._http.get = AsyncMock(side_effect=ConnectionError("down"))
    elif failure == "http500":
        s._http.get = AsyncMock(return_value=_resp(500))
    elif failure == "no_equity":
        s._http.get = AsyncMock(return_value=_resp(200, {"configured": True, "equity": None}))
    else:
        s._http.get = AsyncMock(return_value=_resp(200, ["not", "a", "dict"]))
    with pytest.raises(RuntimeError, match="equity could not be read"):
        _value(s, {"AAPL": 10.0}, {"AAPL": 100.0})


def test_failed_read_keeps_the_old_fallback_when_off():
    s = _sched(False, fallback_portfolio_value=42.0)
    s._http.get = AsyncMock(side_effect=ConnectionError("down"))
    assert _value(s) == 42.0


def test_unconfigured_broker_still_uses_placeholder_when_on():
    """configured:false is a legitimate no-broker setup -- never an abort."""
    s = _sched(True, fallback_portfolio_value=42.0)
    s._http.get = AsyncMock(return_value=_resp(200, {"configured": False}))
    assert _value(s) == 42.0
    assert _value(s, {"AAPL": 100.0}, {"AAPL": 150.0}) == 15_000.0


def test_good_read_is_unchanged_when_on():
    s = _sched(True)
    s._http.get = AsyncMock(return_value=_resp(200, {"configured": True, "equity": 250_000.0}))
    assert _value(s) == 250_000.0


def test_cycle_is_marked_failed_and_places_no_orders_when_equity_read_fails(monkeypatch):
    monkeypatch.setattr("vinu_live.scheduler.asyncio.sleep", AsyncMock())  # a mutated run must fail fast, not wait on TWAP delays
    s = _sched(True)

    async def _get(url, **kw):
        if "/portfolio/state" in url:
            return _resp(200, {"weights": [{"symbol": "AAPL", "target_weight": 0.1}]})
        if "/broker/positions" in url:
            return _resp(200, [])
        if "/broker/account" in url:
            raise ConnectionError("account down")
        if "/candles/" in url:
            return _resp(200, {"data": [{"close": 100.0, "bar_ts": 1_700_000_000}]})
        return _resp(200, {})

    s._http.get = AsyncMock(side_effect=_get)
    s._http.post = AsyncMock()
    result = asyncio.run(s.cycle())
    assert result["status"] == "failed"
    assert not any("/broker/order" in c.args[0] for c in s._http.post.call_args_list)   # no order; only the loud notification goes out
