"""features-logic-checking: from the portfolio's answer to the shares ordered, worked out by hand.

The portfolio's daily allocation says (account equity 100,000):
    strat_a on AAPL  target weight 0.6867        strat_b on MSFT  target weight 0.3133
and how much of the account may be deployed (`deployable_equity`): 90,000 normally, 45,000 after a drawdown "halve",
0 after a "flat". The scheduler scales each weight by deployable / equity, the translator turns weight into shares
(weight x portfolio value / price, rounded to the NEAREST whole share, half up), and the execution planner cuts the
order into TWAP slices.

  normal  fraction 0.90: AAPL 0.6867 x 0.90 = 0.61803 -> 61,803 / 200 = 309.015 -> 309 shares
                         MSFT 0.3133 x 0.90 = 0.28197 -> 28,197 / 400 =  70.49  ->  70 shares   (89,800 deployed <= 90,000)
  halve   fraction 0.45: AAPL 0.309015 -> 30,901.5 / 200 = 154.5075 -> 155 shares;  MSFT 0.140985 -> 14,098.5 / 400 = 35.25 -> 35
  flat    fraction 0.00: both weights 0 -> nothing to buy, and anything already held is sold
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.config import LiveConfig
from vinu_live.execution import plan_twap
from vinu_live.scheduler import LiveScheduler
from vinu_live.signal_translator import SignalTranslator

EQUITY = 100_000.0
PRICES = {"AAPL": 200.0, "MSFT": 400.0}


def _allocation(deployable: float) -> dict:
    return {
        "status": "ok", "account_equity": EQUITY, "deployable_equity": deployable,
        "weights": [
            {"name": "strat_a", "symbol": "AAPL", "target_weight": 0.6867},
            {"name": "strat_b", "symbol": "MSFT", "target_weight": 0.3133},
        ],
    }


def _portfolio(tmp_path, deployable: float) -> dict:
    s = LiveScheduler(LiveConfig(data_root=tmp_path, scheduler_use_daily_allocation=True))
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = _allocation(deployable)
    s._http = MagicMock()
    s._http.get = AsyncMock(return_value=resp)
    return asyncio.run(s._fetch_portfolio())


def _orders(portfolio: dict, positions: dict | None = None) -> dict[str, tuple[str, float]]:
    out = SignalTranslator().translate(portfolio["weights"], positions or {}, EQUITY, PRICES)
    return {i.symbol: (i.side, i.qty) for i in out}


def test_normal_day_buys_309_and_70_shares(tmp_path):
    p = _portfolio(tmp_path, 90_000.0)
    assert p["deployable_fraction"] == pytest.approx(0.9) and p["allocation_source"] == "daily_allocation"
    assert [round(w["target_weight"], 5) for w in p["weights"]] == [0.61803, 0.28197]
    assert _orders(p) == {"AAPL": ("buy", 309.0), "MSFT": ("buy", 70.0)}
    assert 309 * 200.0 + 70 * 400.0 == 89_800.0


def test_after_a_drawdown_halve_only_half_the_capital_is_deployed(tmp_path):
    p = _portfolio(tmp_path, 45_000.0)
    assert p["deployable_fraction"] == pytest.approx(0.45)
    assert _orders(p) == {"AAPL": ("buy", 155.0), "MSFT": ("buy", 35.0)}


def test_after_a_flat_nothing_is_bought_and_what_is_held_is_sold(tmp_path):
    p = _portfolio(tmp_path, 0.0)
    assert p["deployable_fraction"] == 0.0
    assert _orders(p) == {}                                   # no instruction: nothing to buy
    assert _orders(p, {"AAPL": 309.0}) == {"AAPL": ("sell", 309.0)}   # held and no longer targeted: closed to zero


def test_the_order_is_cut_into_twap_slices_that_add_up(tmp_path):
    instructions = SignalTranslator().translate(_portfolio(tmp_path, 90_000.0)["weights"], {}, EQUITY, PRICES)
    aapl = [i for i in instructions if i.symbol == "AAPL"]
    plan = plan_twap(aapl, n_slices=6)
    qty = [s.qty for s in plan.slices]
    assert sum(qty) == 309.0 and len(qty) == 6
    assert qty == [51.0, 51.0, 51.0, 51.0, 51.0, 54.0]       # 309 // 6 = 51 each, the 3 left over join the last slice


def test_netting_opposite_strategies_on_one_symbol_orders_only_the_net():
    """strategy a wants +2% of the account in AAPL, strategy b wants -1%: one order for the net +1% = 1,000 / 200 = 5."""
    t = SignalTranslator()
    out = t.translate([{"name": "a", "symbol": "AAPL", "target_weight": 0.02},
                       {"name": "b", "symbol": "AAPL", "target_weight": -0.01}], {}, EQUITY, PRICES)
    assert [(i.symbol, i.side, i.qty) for i in out] == [("AAPL", "buy", 5.0)]


def test_known_limit_rounding_to_the_nearest_share_can_overshoot_the_deployable_money():
    """Pins today's rule (decision D9 in features-logic-checking/00): one name with the whole 0.9 fraction on a 7,000
    share: 90,000 / 7,000 = 12.857 -> 13 shares = 91,000, which is 1,000 above the deployable 90,000. The overshoot is
    always under half a share per symbol, which matters on a small account holding expensive shares."""
    out = SignalTranslator().translate(
        [{"name": "s", "symbol": "BIG", "target_weight": 0.9}], {}, EQUITY, {"BIG": 7_000.0},
    )
    assert [(i.symbol, i.side, i.qty) for i in out] == [("BIG", "buy", 13.0)]
    assert out[0].qty * 7_000.0 - 0.9 * EQUITY == pytest.approx(1_000.0)
