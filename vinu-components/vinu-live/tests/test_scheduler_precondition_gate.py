"""inconsistencies v1 A8 (the-inconsistencies-v2, Phase 4): the scheduler refuses an EXECUTE whose
`precondition_held` is False. Opt-in `precondition_enforcing_enabled` (default off); None / unknown passes."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_live.breaker.engine import BreakerVerdict
from vinu_live.config import LiveConfig
from vinu_live.live_decision.schema import LiveDecisionRecord
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    list_open_positions,
    list_unapplied_executes,
    record_live_decision,
)
from vinu_live.scheduler import LiveScheduler


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


def _record(tmp_path, held, ticker="AAPL", strategy_id="sma_cross", bar_ts=1000):
    backend = LiveDecisionBackend(str(tmp_path / "live_decision.db"))
    try:
        record_live_decision(backend, LiveDecisionRecord(
            ticker=ticker, strategy_id=strategy_id, trigger_id=f"t{bar_ts}", bar_ts=bar_ts, decision="EXECUTE",
            precondition_held=held, reasoning="r", raw_content="c",
        ))
    finally:
        backend.close()


def _sched(tmp_path, on):
    s = LiveScheduler(LiveConfig(data_root=tmp_path, twap_slices=1, precondition_enforcing_enabled=on))
    s._http = MagicMock()

    async def _get(url, **kw):
        if "/portfolio/state" in url:
            return _resp(200, {"status": "empty", "weights": []})
        if "/strategy/strategies/" in url:
            return _resp(200, {"live_decision_position_size": 0.05})
        if "/broker/positions" in url:
            return _resp(200, [])
        if "/broker/account" in url:
            return _resp(200, {"configured": False})
        if "/candles/" in url:
            return _resp(200, {"data": [{"close": 150.0}]})
        raise AssertionError(url)

    s._http.get = AsyncMock(side_effect=_get)
    s._http.post = AsyncMock(return_value=_resp(200))
    return s


def _run(s):
    with patch("vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.ALLOW, None)), \
         patch("vinu_live.scheduler.asyncio.sleep", AsyncMock()), \
         patch("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None)):
        return asyncio.run(s.cycle())


def test_flag_defaults_off_and_reads_env(monkeypatch):
    assert LiveConfig().precondition_enforcing_enabled is False
    monkeypatch.setenv("VINU_LIVE_PRECONDITION_ENFORCING_ENABLED", "true")
    assert LiveConfig.from_env().precondition_enforcing_enabled is True


def test_on_a_false_precondition_opens_no_position_and_places_no_order(tmp_path):
    _record(tmp_path, held=False)
    s = _sched(tmp_path, on=True)
    r = _run(s)
    assert list_open_positions(s._live_decision_backend) == []
    assert r["status"] == "skipped_no_weights"
    assert r["precondition_blocked"][0]["ticker"] == "AAPL" and r["precondition_blocked"][0]["strategy_id"] == "sma_cross"
    s._http.post.assert_not_called()


def test_on_the_refused_decision_is_final_not_retried(tmp_path):
    _record(tmp_path, held=False)
    s = _sched(tmp_path, on=True)
    _run(s)
    assert list_unapplied_executes(s._live_decision_backend) == []
    assert "precondition_blocked" not in _run(s)           # nothing left to refuse next cycle


@pytest.mark.parametrize("held", [True, None])
def test_on_a_true_or_unknown_precondition_still_trades(tmp_path, held):
    _record(tmp_path, held=held)
    s = _sched(tmp_path, on=True)
    r = _run(s)
    assert len(list_open_positions(s._live_decision_backend)) == 1
    assert r["status"] == "ok" and r["submitted"] and "precondition_blocked" not in r


def test_off_a_false_precondition_trades_exactly_as_before(tmp_path):
    _record(tmp_path, held=False)
    s = _sched(tmp_path, on=False)
    r = _run(s)
    assert len(list_open_positions(s._live_decision_backend)) == 1
    assert r["status"] == "ok" and "precondition_blocked" not in r


def test_on_only_the_false_one_of_two_is_refused(tmp_path):
    _record(tmp_path, held=False, ticker="AAPL", strategy_id="s_a", bar_ts=1)
    _record(tmp_path, held=True, ticker="MSFT", strategy_id="s_b", bar_ts=2)
    s = _sched(tmp_path, on=True)
    r = _run(s)
    assert [p.ticker for p in list_open_positions(s._live_decision_backend)] == ["MSFT"]
    assert [b["ticker"] for b in r["precondition_blocked"]] == ["AAPL"]


def test_on_an_already_open_position_is_untouched(tmp_path):
    _record(tmp_path, held=True, bar_ts=1)
    s = _sched(tmp_path, on=True)
    _run(s)
    _record(tmp_path, held=False, bar_ts=2)                 # a later false-precondition EXECUTE for the same pair
    _run(s)
    assert len(list_open_positions(s._live_decision_backend)) == 1
