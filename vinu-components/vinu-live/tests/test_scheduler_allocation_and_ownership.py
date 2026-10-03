"""logic-audit-2026-10-02 A1 + A2 (the-inconsistencies-v2, Phase 4), both opt-in and default off.

A1 `scheduler_use_daily_allocation`: the scheduler sizes from /portfolio/daily-allocation, scaled by
    deployable_equity / account_equity, instead of the raw /portfolio/state weights.
A2 `scheduler_respect_trade_plan_symbols`: symbols the trade-plan orchestrator owns (open book position
    or ACTIVE trade_plan artifact) are neither targeted nor liquidated by the scheduler.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.book.positions import open_position
from vinu_live.breaker.engine import BreakerVerdict
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


def _sched(tmp_path, **cfg) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(data_root=tmp_path, **cfg))
    s._http = MagicMock()
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    s._check_breaker = AsyncMock(return_value=(BreakerVerdict.ALLOW, ""))
    return s


def _alloc(weights, equity=100_000.0, deployable=100_000.0, status="ok"):
    return {"status": status, "weights": weights, "account_equity": equity, "deployable_equity": deployable}


def _router(*, state=None, alloc=None, positions=(), plans=None, plan_status=200, equity=100_000.0):
    """Fake HTTP: routes by URL. `alloc=None` -> daily-allocation returns 500."""
    async def _get(url, params=None, **kw):
        if "/portfolio/daily-allocation" in url:
            return _resp(500) if alloc is None else _resp(200, alloc)
        if "/portfolio/state" in url:
            return _resp(200, state if state is not None else {"status": "ok", "weights": []})
        if "/broker/positions" in url:
            return _resp(200, [{"symbol": s, "qty": q} for s, q in positions])
        if "/broker/account" in url:
            return _resp(200, {"configured": True, "equity": equity})
        if "/research/artifacts" in url:
            if plan_status != 200 or plans is None:
                return _resp(plan_status if plan_status != 200 else 200, [])
            return _resp(200, [{"artifact_id": f"a{i}"} for i in range(len(plans))])
        if "/research/trade-plan/" in url:
            i = int(url.rsplit("/a", 1)[1])
            return _resp(200, {"trade_plan_data": json.dumps({"symbol": plans[i]})})
        if "/candles/" in url:
            return _resp(200, {"data": [{"close": 100.0, "bar_ts": 1_700_000_000}]})
        return _resp(404)
    return AsyncMock(side_effect=_get)


def _orders(s):
    return [c.kwargs["json"] for c in s._http.post.call_args_list if "/broker/order" in c.args[0]]


def _run(s, monkeypatch):
    monkeypatch.setattr("vinu_live.scheduler.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None))
    return asyncio.run(s.cycle())


# ====================================================================== A1

def test_flags_default_off_and_read_env(monkeypatch):
    c = LiveConfig()
    assert c.scheduler_use_daily_allocation is False and c.scheduler_respect_trade_plan_symbols is False
    monkeypatch.setenv("VINU_LIVE_SCHEDULER_USE_DAILY_ALLOCATION", "1")
    monkeypatch.setenv("VINU_LIVE_SCHEDULER_RESPECT_TRADE_PLAN_SYMBOLS", "true")
    c = LiveConfig.from_env()
    assert c.scheduler_use_daily_allocation and c.scheduler_respect_trade_plan_symbols


def _fetch(s):
    return asyncio.run(s._fetch_portfolio())


def test_a1_off_reads_state_only(tmp_path):
    s = _sched(tmp_path)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.3}]}, alloc=_alloc([]))
    out = _fetch(s)
    assert out["weights"][0]["target_weight"] == 0.3
    assert not any("daily-allocation" in c.args[0] for c in s._http.get.call_args_list)


@pytest.mark.parametrize("deployable,expected", [
    (100_000.0, 0.4),     # ok: unchanged
    (50_000.0, 0.2),      # drawdown "halve": half the capital
    (0.0, 0.0),           # flat / halt: no capital
    (200_000.0, 0.4),     # more than equity is clamped, never levers up
])
def test_a1_scales_weights_by_the_deployable_fraction(tmp_path, deployable, expected):
    s = _sched(tmp_path, scheduler_use_daily_allocation=True)
    s._http.get = _router(alloc=_alloc([{"symbol": "AAPL", "target_weight": 0.4, "name": "x"}], deployable=deployable))
    out = _fetch(s)
    assert out["weights"][0]["target_weight"] == pytest.approx(expected)
    assert out["allocation_source"] == "daily_allocation"
    assert out["weights"][0]["name"] == "x"          # other fields pass through


def test_a1_missing_equity_or_deployable_means_no_scaling(tmp_path):
    for eq, dep in [(None, 50_000.0), (100_000.0, None), (0.0, 0.0)]:
        s = _sched(tmp_path, scheduler_use_daily_allocation=True)
        s._http.get = _router(alloc=_alloc([{"symbol": "AAPL", "target_weight": 0.4}], equity=eq, deployable=dep))
        assert _fetch(s)["weights"][0]["target_weight"] == pytest.approx(0.4)


def test_a1_falls_back_to_state_when_daily_allocation_fails(tmp_path):
    s = _sched(tmp_path, scheduler_use_daily_allocation=True)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.3}]}, alloc=None)
    out = _fetch(s)
    assert out["weights"][0]["target_weight"] == 0.3 and "allocation_source" not in out


def test_a1_an_empty_allocation_yields_no_weights_not_a_fallback(tmp_path):
    s = _sched(tmp_path, scheduler_use_daily_allocation=True)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.3}]},
                          alloc={"status": "empty", "weights": []})
    assert _fetch(s)["weights"] == []


def test_a1_cycle_places_half_the_order_when_the_drawdown_ladder_halves(tmp_path, monkeypatch):
    def qty_for(deployable):
        s = _sched(tmp_path, scheduler_use_daily_allocation=True, twap_slices=1)
        s._http.get = _router(alloc=_alloc([{"symbol": "AAPL", "target_weight": 0.5}], deployable=deployable))
        r = _run(s, monkeypatch)
        assert r["status"] == "ok" and r["allocation_source"] == "daily_allocation"
        return sum(o["qty"] for o in _orders(s))
    full, half = qty_for(100_000.0), qty_for(50_000.0)
    assert full > 0 and half == pytest.approx(full / 2)


def test_a1_flat_ladder_sells_the_book_down(tmp_path, monkeypatch):
    s = _sched(tmp_path, scheduler_use_daily_allocation=True, twap_slices=1)
    s._http.get = _router(alloc=_alloc([{"symbol": "AAPL", "target_weight": 0.5}], deployable=0.0), positions=[("AAPL", 100.0)])
    r = _run(s, monkeypatch)
    assert r["deployable_fraction"] == 0.0
    orders = _orders(s)
    assert orders and all(o["side"] == "sell" and o["symbol"] == "AAPL" for o in orders)


def test_a1_off_cycle_ignores_the_allocation_entirely(tmp_path, monkeypatch):
    s = _sched(tmp_path, twap_slices=1)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.5}]},
                          alloc=_alloc([{"symbol": "AAPL", "target_weight": 0.5}], deployable=0.0))
    r = _run(s, monkeypatch)
    assert "allocation_source" not in r and any(o["side"] == "buy" for o in _orders(s))


# ====================================================================== A2

def _own_book_position(s, symbol="MSFT"):
    open_position(s._book, symbol, "long", 10.0, 100.0)


def test_a2_off_a_symbol_in_both_lists_is_sized_by_the_scheduler_too(tmp_path, monkeypatch):
    """The live hazard when the flag is off: the scheduler trades a symbol the orchestrator owns."""
    s = _sched(tmp_path, twap_slices=1)
    _own_book_position(s)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "MSFT", "target_weight": 0.5}]},
                          positions=[("MSFT", 10.0)])
    _run(s, monkeypatch)
    assert any(o["symbol"] == "MSFT" for o in _orders(s))


def test_known_finding_flag_off_a_held_but_untargeted_position_is_never_priced_so_never_sold(tmp_path, monkeypatch):
    """FINDING while building A2: `_fetch_prices` prices only symbols that have a target, so SignalTranslator skips every
    held-but-untargeted position ("No usable price") -- the documented closing of a retired strategy's symbol never
    happened. Left as is when the flag is OFF (old behavior); the flag-ON rules below fix it for scheduler-owned symbols."""
    s = _sched(tmp_path, twap_slices=1)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.5}]},
                          positions=[("OLD", 10.0)], plans=[])
    _run(s, monkeypatch)
    assert not any(o["symbol"] == "OLD" for o in _orders(s))


def test_a2_on_a_book_owned_symbol_is_never_sold(tmp_path, monkeypatch):
    s = _sched(tmp_path, twap_slices=1, scheduler_respect_trade_plan_symbols=True)
    _own_book_position(s)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.5}]},
                          positions=[("MSFT", 10.0)], plans=[])
    r = _run(s, monkeypatch)
    assert not any(o["symbol"] == "MSFT" for o in _orders(s))
    assert r["ownership"]["positions_left_alone"] == ["MSFT"]
    assert any(o["symbol"] == "AAPL" and o["side"] == "buy" for o in _orders(s))     # normal targets still traded


def test_a2_on_an_active_plan_symbol_is_owned_even_before_the_book_has_a_position(tmp_path, monkeypatch):
    s = _sched(tmp_path, twap_slices=1, scheduler_respect_trade_plan_symbols=True)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.5}]},
                          positions=[("NVDA", 5.0)], plans=["nvda"])
    r = _run(s, monkeypatch)
    assert not any(o["symbol"] == "NVDA" for o in _orders(s))
    assert r["ownership"]["positions_left_alone"] == ["NVDA"]


def test_a2_on_a_symbol_in_both_lists_is_sized_by_the_orchestrator_only(tmp_path, monkeypatch):
    s = _sched(tmp_path, twap_slices=1, scheduler_respect_trade_plan_symbols=True)
    s._http.get = _router(state={"status": "ok", "weights": [
        {"symbol": "AAPL", "target_weight": 0.5}, {"symbol": "MSFT", "target_weight": 0.5}]},
        positions=[], plans=["MSFT"])
    r = _run(s, monkeypatch)
    assert r["ownership"]["targets_skipped_orchestrator_owned"] == ["MSFT"]
    assert {o["symbol"] for o in _orders(s)} == {"AAPL"}


def test_a2_on_unreadable_plans_nothing_untargeted_is_liquidated(tmp_path, monkeypatch):
    s = _sched(tmp_path, twap_slices=1, scheduler_respect_trade_plan_symbols=True)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.5}]},
                          positions=[("OLD", 10.0)], plan_status=500)
    r = _run(s, monkeypatch)
    assert not any(o["symbol"] == "OLD" for o in _orders(s))
    assert r["ownership"]["ownership_unknown"] is True and r["ownership"]["positions_left_alone"] == ["OLD"]
    assert any(o["symbol"] == "AAPL" for o in _orders(s))          # targeted symbols still trade


def test_a2_a_failure_in_the_ownership_check_leaves_inputs_untouched(tmp_path, monkeypatch):
    s = _sched(tmp_path, twap_slices=1, scheduler_respect_trade_plan_symbols=True)
    s._fetch_trade_plan_symbols = AsyncMock(side_effect=RuntimeError("boom"))
    tw = [{"symbol": "AAPL", "target_weight": 0.5}]
    out_tw, out_pos, info = asyncio.run(s._apply_symbol_ownership(tw, {"X": 1.0}))
    assert out_tw == tw and out_pos == {"X": 1.0} and info == {}


def test_a2_owned_positions_are_removed_from_what_the_translator_sees(tmp_path):
    """Direct check (the cycle tests cannot see this today because untargeted symbols are never priced):
    once pricing is fixed, an owned position must already be invisible to the liquidation loop."""
    s = _sched(tmp_path, scheduler_respect_trade_plan_symbols=True)
    _own_book_position(s, "MSFT")
    s._http.get = _router(plans=["nvda"])
    tw = [{"symbol": "AAPL", "target_weight": 0.5}, {"symbol": "MSFT", "target_weight": 0.5}]
    out_tw, out_pos, info = asyncio.run(s._apply_symbol_ownership(tw, {"MSFT": 10.0, "NVDA": 5.0, "OLD": 1.0}))
    assert out_pos == {}                                          # OLD is in nobody's ledger: a hand-placed holding, left alone too
    assert [t["symbol"] for t in out_tw] == ["AAPL"]
    assert info["positions_left_alone"] == ["MSFT", "NVDA", "OLD"] and info["targets_skipped_orchestrator_owned"] == ["MSFT"]


# ====================================================================== retired symbols: close what the scheduler opened

def _bought(s, symbol, outcome="submitted", side="buy"):
    s._execution_log.record(symbol=symbol, side=side, qty=1.0, outcome=outcome)


def _orphan_cycle(tmp_path, monkeypatch, *, ledger=(), adopted="", plans=(), plan_status=200, positions=(("OLD", 10.0),)):
    s = _sched(tmp_path, twap_slices=1, scheduler_respect_trade_plan_symbols=True, scheduler_adopted_symbols=adopted)
    for sym in ledger:
        _bought(s, sym)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.5}]},
                          positions=list(positions), plans=list(plans), plan_status=plan_status)
    r = _run(s, monkeypatch)
    return s, r


def test_a_retired_symbol_the_scheduler_bought_is_closed(tmp_path, monkeypatch):
    s, r = _orphan_cycle(tmp_path, monkeypatch, ledger=["OLD"])
    sells = [o for o in _orders(s) if o["symbol"] == "OLD"]
    assert sells and all(o["side"] == "sell" for o in sells)
    assert r["ownership"]["orphans_to_liquidate"] == ["OLD"]


def test_a_holding_the_scheduler_never_bought_is_left_alone(tmp_path, monkeypatch):
    """The hand-placed holding in the account: no ledger entry, so it is never touched."""
    s, r = _orphan_cycle(tmp_path, monkeypatch, ledger=[])
    assert not any(o["symbol"] == "OLD" for o in _orders(s))
    assert r["ownership"]["positions_left_alone"] == ["OLD"] and "orphans_to_liquidate" not in r["ownership"]


def test_only_accepted_buys_count_as_the_scheduler_opening_it(tmp_path, monkeypatch):
    s = _sched(tmp_path, twap_slices=1, scheduler_respect_trade_plan_symbols=True)
    _bought(s, "OLD", outcome="rejected")
    _bought(s, "OLD", outcome="skipped")
    _bought(s, "OLD", outcome="submitted", side="sell")
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.5}]},
                          positions=[("OLD", 10.0)], plans=[])
    _run(s, monkeypatch)
    assert not any(o["symbol"] == "OLD" for o in _orders(s))


def test_adopted_symbols_cover_positions_opened_before_the_ledger_existed(tmp_path, monkeypatch):
    s, r = _orphan_cycle(tmp_path, monkeypatch, adopted=" old , other ")
    assert any(o["symbol"] == "OLD" and o["side"] == "sell" for o in _orders(s))


def test_an_orchestrator_owned_symbol_is_never_closed_even_if_the_scheduler_once_bought_it(tmp_path, monkeypatch):
    s, r = _orphan_cycle(tmp_path, monkeypatch, ledger=["OLD"], plans=["old"])
    assert not any(o["symbol"] == "OLD" for o in _orders(s))
    assert r["ownership"]["positions_left_alone"] == ["OLD"]


def test_unknown_ownership_closes_nothing_even_for_the_schedulers_own_symbol(tmp_path, monkeypatch):
    s, r = _orphan_cycle(tmp_path, monkeypatch, ledger=["OLD"], plan_status=500)
    assert not any(o["symbol"] == "OLD" for o in _orders(s))
    assert r["ownership"]["ownership_unknown"] is True


def test_a_still_targeted_symbol_is_not_an_orphan(tmp_path, monkeypatch):
    s, r = _orphan_cycle(tmp_path, monkeypatch, ledger=["AAPL"], positions=[("AAPL", 10.0)])
    assert "orphans_to_liquidate" not in (r.get("ownership") or {})


def test_without_the_ledger_nothing_is_closed(tmp_path, monkeypatch):
    s = _sched(tmp_path, twap_slices=1, scheduler_respect_trade_plan_symbols=True, execution_log_enabled=False)
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.5}]},
                          positions=[("OLD", 10.0)], plans=[])
    _run(s, monkeypatch)
    assert not any(o["symbol"] == "OLD" for o in _orders(s))


def test_flag_off_the_ledger_alone_never_closes_anything(tmp_path, monkeypatch):
    s = _sched(tmp_path, twap_slices=1)
    _bought(s, "OLD")
    s._http.get = _router(state={"status": "ok", "weights": [{"symbol": "AAPL", "target_weight": 0.5}]}, positions=[("OLD", 10.0)])
    _run(s, monkeypatch)
    assert not any(o["symbol"] == "OLD" for o in _orders(s))


def test_adopted_symbols_flag_defaults_empty_and_reads_env(monkeypatch):
    assert LiveConfig().scheduler_adopted_symbols == ""
    monkeypatch.setenv("VINU_LIVE_SCHEDULER_ADOPTED_SYMBOLS", "XYZ,ABC")
    assert LiveConfig.from_env().scheduler_adopted_symbols == "XYZ,ABC"
