"""logic-audit-2026-10-02 A6 (the-inconsistencies-v2, Phase 4): the scheduler's breaker can read the
BROKER account (positions it actually trades, equity-based daily P&L including unrealized moves)
instead of the trade-plan book and realized-only loss. Opt-in `scheduler_breaker_uses_broker_account`.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.breaker.engine import BreakerVerdict, check_limits
from vinu_live.breaker.limits import BreakerState
from vinu_live.config import LiveConfig
from vinu_live.scheduler import LiveScheduler


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.raise_for_status = MagicMock()
    return r


def _sched(tmp_path, on: bool, **cfg) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(data_root=tmp_path, scheduler_breaker_uses_broker_account=on, **cfg))
    s._http = MagicMock()
    s._http.post = AsyncMock(return_value=_resp(200, {}))

    async def _get(url, params=None, **kw):
        if "/candles/" in url:
            return _resp(200, {"data": [{"close": 100.0, "bar_ts": 1_700_000_000}]})
        return _resp(404)

    s._http.get = AsyncMock(side_effect=_get)
    return s


def _check(s, equity=100_000.0, positions=None, real=True):
    s._equity_is_real = real
    return asyncio.run(s._check_breaker(equity, broker_positions=positions))


# ------------------------------------------------------------------ engine

def test_flag_defaults_on_and_env_can_turn_it_off(monkeypatch):
    # ON by default since 2026-10-04 (features-logic-checking): paper trading should behave like real money.
    assert LiveConfig().scheduler_breaker_uses_broker_account is True
    monkeypatch.delenv("VINU_LIVE_SCHEDULER_BREAKER_USES_BROKER_ACCOUNT", raising=False)
    assert LiveConfig.from_env().scheduler_breaker_uses_broker_account is True
    monkeypatch.setenv("VINU_LIVE_SCHEDULER_BREAKER_USES_BROKER_ACCOUNT", "false")
    assert LiveConfig.from_env().scheduler_breaker_uses_broker_account is False


def test_check_limits_uses_the_explicit_positions_instead_of_the_book(tmp_path):
    from types import SimpleNamespace

    from vinu_live.book.positions import init_book

    book = init_book(str(tmp_path / "b.db"))
    many = [SimpleNamespace(symbol=f"S{i}", qty=1.0, side="long") for i in range(25)]
    assert check_limits(book, {}, 100_000.0, 0.0, state=BreakerState())[0] == BreakerVerdict.ALLOW   # empty book
    verdict, reason = check_limits(book, {}, 100_000.0, 0.0, state=BreakerState(), positions=many)
    assert verdict == BreakerVerdict.HALT and "Position count 25" in reason


# ------------------------------------------------------------------ scheduler: positions

def _broker_positions(n, qty=1.0):
    return {f"S{i}": qty for i in range(n)}


def test_off_the_breaker_is_blind_to_broker_positions(tmp_path):
    s = _sched(tmp_path, on=False)
    assert _check(s, positions=_broker_positions(25))[0] == BreakerVerdict.ALLOW     # the blind spot, unchanged when off


def test_on_too_many_broker_positions_halts(tmp_path):
    s = _sched(tmp_path, on=True)
    verdict, reason = _check(s, positions=_broker_positions(25))
    assert verdict == BreakerVerdict.HALT and "Position count 25" in reason


def test_on_leverage_is_measured_on_broker_positions_and_shorts_count_as_gross(tmp_path):
    s = _sched(tmp_path, on=True)
    # 3,000 shares at $100 = $300k gross on $100k equity = 3x > 2x; one short leg must still add to gross
    verdict, reason = _check(s, positions={"AAA": 2_000.0, "BBB": -1_000.0})
    assert verdict == BreakerVerdict.HALT and "Leverage 3.00x" in reason


def test_on_a_normal_account_is_allowed(tmp_path):
    s = _sched(tmp_path, on=True)
    assert _check(s, positions={"AAA": 100.0, "BBB": -50.0})[0] == BreakerVerdict.ALLOW


def test_on_without_broker_positions_falls_back_to_the_book(tmp_path):
    s = _sched(tmp_path, on=True)
    assert _check(s, positions=None)[0] == BreakerVerdict.ALLOW


# ------------------------------------------------------------------ scheduler: equity-based daily P&L

def test_on_an_unrealized_equity_drop_trips_the_daily_loss_limit(tmp_path):
    s = _sched(tmp_path, on=True)
    assert _check(s, equity=100_000.0)[0] == BreakerVerdict.ALLOW          # first sight of the day: baseline
    verdict, reason = _check(s, equity=93_000.0)                            # -7% with no closed trade at all
    assert verdict == BreakerVerdict.HALT and "Daily loss 7.5%" in reason  # engine divides by CURRENT equity (7,000 / 93,000)


def test_off_the_same_equity_drop_is_invisible(tmp_path):
    s = _sched(tmp_path, on=False)
    _check(s, equity=100_000.0)
    assert _check(s, equity=93_000.0)[0] == BreakerVerdict.ALLOW
    assert not (tmp_path / "breaker_day_equity.json").exists()


def test_on_a_small_move_or_a_gain_does_not_halt(tmp_path):
    s = _sched(tmp_path, on=True)
    _check(s, equity=100_000.0)
    assert _check(s, equity=97_000.0)[0] == BreakerVerdict.ALLOW            # -3% < 5%
    s2 = _sched(tmp_path / "other", on=True)
    _check(s2, equity=100_000.0)
    assert _check(s2, equity=150_000.0)[0] == BreakerVerdict.ALLOW


def test_the_day_baseline_survives_a_restart(tmp_path):
    _check(_sched(tmp_path, on=True), equity=100_000.0)
    verdict, _ = _check(_sched(tmp_path, on=True), equity=90_000.0)       # a brand-new scheduler object
    assert verdict == BreakerVerdict.HALT


def test_a_new_utc_day_resets_the_baseline(tmp_path):
    (tmp_path).mkdir(exist_ok=True)
    (tmp_path / "breaker_day_equity.json").write_text(json.dumps({"date": "2020-01-01", "equity": 200_000.0}))
    s = _sched(tmp_path, on=True)
    assert _check(s, equity=100_000.0)[0] == BreakerVerdict.ALLOW          # stale baseline ignored, not -50%
    assert json.loads((tmp_path / "breaker_day_equity.json").read_text())["equity"] == 100_000.0


def test_a_placeholder_equity_never_creates_a_baseline(tmp_path):
    s = _sched(tmp_path, on=True)
    _check(s, equity=1_000_000.0, real=False)
    assert not (tmp_path / "breaker_day_equity.json").exists()


def test_a_broken_baseline_file_falls_back_to_realized_pnl_and_never_raises(tmp_path):
    (tmp_path / "breaker_day_equity.json").write_text("{not json")
    s = _sched(tmp_path, on=True)
    assert _check(s, equity=93_000.0)[0] == BreakerVerdict.ALLOW


# ------------------------------------------------------------------ the whole cycle

def test_cycle_halts_on_an_account_drawdown_when_on(tmp_path, monkeypatch):
    monkeypatch.setattr("vinu_live.scheduler.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None))
    equity = {"v": 100_000.0}

    def make(on):
        s = _sched(tmp_path / ("on" if on else "off"), on=on, twap_slices=1)

        async def _get(url, params=None, **kw):
            if "/portfolio/state" in url:
                return _resp(200, {"weights": [{"symbol": "AAPL", "target_weight": 0.1}]})
            if "/broker/positions" in url:
                return _resp(200, [])
            if "/broker/account" in url:
                return _resp(200, {"configured": True, "equity": equity["v"]})
            if "/candles/" in url:
                return _resp(200, {"data": [{"close": 100.0, "bar_ts": 1_700_000_000}]})
            return _resp(404)

        s._http.get = AsyncMock(side_effect=_get)
        return s

    on, off = make(True), make(False)
    for s in (on, off):
        equity["v"] = 100_000.0
        assert asyncio.run(s.cycle())["status"] == "ok"
        equity["v"] = 90_000.0
    r_on, r_off = asyncio.run(on.cycle()), asyncio.run(off.cycle())
    assert r_on["status"] == "halted_by_breaker" and "Daily loss" in r_on["breaker_reason"]
    assert r_off["status"] == "ok"
