"""logic-audit-2026-10-02 A4 (the-inconsistencies-v2, plan item 2.2): the opt-in
entries-only guards on LiveScheduler's portfolio/live-decision path.

The trade-plan orchestrator already pauses NEW exposure on a consecutive-loss
cooldown, a stale price feed and extreme realized vol; this path had none of
them. These tests pin: off by default, entries-only (a reduce/close is never
held back), each guard blocks, and any guard failure fails open.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_live.breaker.engine import BreakerVerdict
from vinu_live.config import LiveConfig
from vinu_live.scheduler import LiveScheduler
from vinu_live.signal_translator import OrderInstruction
from vinu_live.trade_plan.guards import instruction_increases_exposure


def _instr(symbol="AAPL", side="buy", qty=10.0, current_qty=0.0) -> OrderInstruction:
    return OrderInstruction(
        symbol=symbol, side=side, qty=qty, target_weight=0.0,
        current_qty=current_qty, estimated_value=qty * 100.0,
    )


def _scheduler(tmp_path, *, guards: bool, **cfg) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(data_root=tmp_path, scheduler_entry_guards_enabled=guards, **cfg))
    s._http = MagicMock()
    return s


def _resp(status_code=200, json_body=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body if json_body is not None else {}
    return r


# ----------------------------------------------------------- classifier (pure)

@pytest.mark.parametrize(
    "side,qty,current,expected",
    [
        ("buy", 10, 0, True),        # opens a long
        ("buy", 5, 10, True),        # adds to a long
        ("sell", 4, 10, False),      # trims a long
        ("sell", 10, 10, False),     # closes a long exactly
        ("sell", 25, 10, True),      # flips long -> larger short: net exposure grows
        ("sell", 10, 0, True),       # opens a short
        ("sell", 5, -10, True),      # adds to a short
        ("buy", 4, -10, False),      # covers part of a short
        ("buy", 10, -10, False),     # closes a short exactly
        ("buy", 25, -10, True),      # flips short -> larger long
        ("hold", 1, 0, True),        # unclassifiable -> treated as increasing
    ],
)
def test_instruction_increases_exposure(side, qty, current, expected):
    assert instruction_increases_exposure(side, qty, current) is expected


def test_flip_that_ends_smaller_is_not_an_increase():
    # long 10 -> sell 15 -> short 5: |5| < |10|, exposure shrank
    assert instruction_increases_exposure("sell", 15, 10) is False


# ----------------------------------------------------------- _apply_entry_guards

def test_off_by_default_and_never_touches_the_guards(tmp_path):
    s = _scheduler(tmp_path, guards=False)
    assert LiveConfig().scheduler_entry_guards_enabled is False
    instrs = [_instr()]
    with patch("vinu_live.scheduler.cooldown_active", side_effect=AssertionError("must not run")):
        kept, blocked = asyncio.run(s._apply_entry_guards(instrs))
    assert kept == instrs and blocked == []


def test_cooldown_blocks_increase_but_never_a_reduce(tmp_path):
    s = _scheduler(tmp_path, guards=True)
    buy, sell_reduce = _instr(side="buy", current_qty=0.0), _instr(symbol="MSFT", side="sell", qty=5, current_qty=10)
    with patch("vinu_live.scheduler.cooldown_active", return_value=(True, "cooldown: 2 consecutive losses")):
        kept, blocked = asyncio.run(s._apply_entry_guards([buy, sell_reduce]))
    assert kept == [sell_reduce]
    assert len(blocked) == 1 and blocked[0]["guard"] == "cooldown" and blocked[0]["symbol"] == "AAPL"


def test_stale_price_blocks_increase_only(tmp_path):
    s = _scheduler(tmp_path, guards=True)
    s._last_price_ts["AAPL"] = time.time() - 200 * 3600  # older than the 96h default
    s._last_price_ts["MSFT"] = time.time() - 200 * 3600
    buy = _instr("AAPL", "buy", 10, 0)
    close_msft = _instr("MSFT", "sell", 10, 10)
    with patch("vinu_live.scheduler.cooldown_active", return_value=(False, "")):
        kept, blocked = asyncio.run(s._apply_entry_guards([buy, close_msft]))
    assert kept == [close_msft]
    assert blocked[0]["guard"] == "stale_data" and "exceeds max" in blocked[0]["reason"]


def test_fresh_or_unknown_price_age_passes(tmp_path):
    s = _scheduler(tmp_path, guards=True)
    s._last_price_ts["AAPL"] = time.time() - 3600  # 1h old
    # NVDA has no recorded timestamp at all -> fail open
    instrs = [_instr("AAPL"), _instr("NVDA")]
    with patch("vinu_live.scheduler.cooldown_active", return_value=(False, "")):
        kept, blocked = asyncio.run(s._apply_entry_guards(instrs))
    assert kept == instrs and blocked == []


def test_turbulence_blocks_increase_and_is_not_consulted_for_a_reduce(tmp_path):
    s = _scheduler(tmp_path, guards=True)
    buy, reduce_ = _instr("AAPL", "buy", 10, 0), _instr("MSFT", "sell", 5, 10)
    turb = AsyncMock(return_value=(True, "turbulence: 14d vol 0.090 > 0.050, entries paused"))
    with patch("vinu_live.scheduler.cooldown_active", return_value=(False, "")), \
            patch("vinu_live.scheduler.turbulence_active", turb):
        kept, blocked = asyncio.run(s._apply_entry_guards([buy, reduce_]))
    assert kept == [reduce_]
    assert blocked[0]["guard"] == "turbulence"
    assert turb.await_count == 1 and turb.await_args.args[1] == "AAPL"


def test_a_guard_failure_fails_open(tmp_path):
    s = _scheduler(tmp_path, guards=True)
    instrs = [_instr()]
    with patch("vinu_live.scheduler.cooldown_active", side_effect=RuntimeError("boom")):
        kept, blocked = asyncio.run(s._apply_entry_guards(instrs))
    assert kept == instrs and blocked == []


# ----------------------------------------------------------- prices record bar_ts

def test_fetch_prices_records_bar_ts_and_drops_it_when_missing(tmp_path):
    s = _scheduler(tmp_path, guards=True)
    bars = {"data": [{"close": 150.0, "bar_ts": 1_700_000_000}]}
    s._http.get = AsyncMock(return_value=_resp(json_body=bars))
    prices = asyncio.run(s._fetch_prices([{"symbol": "AAPL"}]))
    assert prices == {"AAPL": 150.0} and s._last_price_ts["AAPL"] == 1_700_000_000.0

    s._http.get = AsyncMock(return_value=_resp(json_body={"data": [{"close": 151.0}]}))
    asyncio.run(s._fetch_prices([{"symbol": "AAPL"}]))
    assert "AAPL" not in s._last_price_ts  # no timestamp -> guard fails open, not on a stale value


# ----------------------------------------------------------- end to end through cycle()

def _wire(s: LiveScheduler, *, positions, weight):
    async def _get(url, **kwargs):
        if "/portfolio/state" in url:
            return _resp(json_body={"weights": [{"symbol": "AAPL", "target_weight": weight}]})
        if "/agent/broker/positions" in url:
            return _resp(json_body=positions)
        if "/agent/broker/account" in url:
            return _resp(json_body={"configured": False})
        if "/stock/quote/" in url or "/stock/events/" in url or "/agent/broker/status" in url:
            return _resp(status_code=404)
        if "/candles/" in url:
            return _resp(json_body={"data": [{"close": 150.0}]})
        raise AssertionError(f"unexpected GET: {url}")

    s._http.get = AsyncMock(side_effect=_get)
    s._http.post = AsyncMock(return_value=_resp(status_code=200))


def test_cycle_holds_back_a_new_buy_and_does_not_raise_false_drift(tmp_path):
    s = _scheduler(tmp_path, guards=True, twap_slices=1)
    _wire(s, positions=[], weight=0.1)
    with patch("vinu_live.scheduler.cooldown_active", return_value=(True, "cooldown: test")), \
            patch("vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.ALLOW, None)):
        result = asyncio.run(s.cycle())
    assert result["status"] == "ok"
    assert result["guard_blocked"][0]["guard"] == "cooldown"
    assert "submitted" not in result  # nothing reached the broker
    assert result["reconciliation"]["n_drifts"] == 0  # a deliberate hold is not drift
    s._http.post.assert_not_called()


def test_cycle_still_sells_to_reduce_while_the_cooldown_is_active(tmp_path):
    s = _scheduler(tmp_path, guards=True, twap_slices=1)
    _wire(s, positions=[{"symbol": "AAPL", "qty": 100}], weight=0.0)
    with patch("vinu_live.scheduler.cooldown_active", return_value=(True, "cooldown: test")), \
            patch("vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.ALLOW, None)):
        result = asyncio.run(s.cycle())
    assert "guard_blocked" not in result
    sells = [o for o in result["submitted"] if o["side"] == "sell"]
    assert sells and sells[0]["symbol"] == "AAPL" and sells[0]["status"] == "submitted"


def test_cycle_with_guards_off_is_unchanged_even_if_cooldown_would_fire(tmp_path):
    s = _scheduler(tmp_path, guards=False, twap_slices=1)
    _wire(s, positions=[], weight=0.1)
    with patch("vinu_live.scheduler.cooldown_active", return_value=(True, "cooldown: test")), \
            patch("vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.ALLOW, None)):
        result = asyncio.run(s.cycle())
    assert "guard_blocked" not in result
    assert [o["side"] for o in result["submitted"]] == ["buy"]
