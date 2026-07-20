import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.config import LiveConfig
from vinu_live.scheduler import LiveScheduler
from vinu_live.signal_translator import OrderInstruction


def _make_scheduler(**config_overrides) -> LiveScheduler:
    config = LiveConfig(**config_overrides)
    scheduler = LiveScheduler(config)
    scheduler._http = MagicMock()
    return scheduler


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    return resp


class TestFetchPrices:
    def test_fetches_latest_close_from_stock_price_api(self) -> None:
        scheduler = _make_scheduler()
        scheduler._http.get = AsyncMock(return_value=_resp(json_body={
            "data": [{"close": 100.0}, {"close": 105.0}]
        }))

        prices = asyncio.run(scheduler._fetch_prices([{"symbol": "AAPL"}]))

        assert prices == {"AAPL": 105.0}
        call = scheduler._http.get.call_args
        assert "/candles/AAPL" in call.args[0]

    def test_missing_symbol_data_is_skipped_not_defaulted(self) -> None:
        scheduler = _make_scheduler()
        scheduler._http.get = AsyncMock(side_effect=ConnectionError("down"))

        prices = asyncio.run(scheduler._fetch_prices([{"symbol": "AAPL"}]))

        assert prices == {}


class TestFetchPortfolioValue:
    def test_uses_account_equity_when_available(self) -> None:
        scheduler = _make_scheduler()
        scheduler._http.get = AsyncMock(return_value=_resp(json_body={
            "configured": True, "equity": 250_000.0,
        }))

        value = asyncio.run(scheduler._fetch_portfolio_value({}, {}))

        assert value == 250_000.0

    def test_falls_back_to_priced_positions_when_no_account(self) -> None:
        scheduler = _make_scheduler()
        scheduler._http.get = AsyncMock(return_value=_resp(json_body={"configured": False}))

        value = asyncio.run(scheduler._fetch_portfolio_value(
            {"AAPL": 100.0}, {"AAPL": 150.0},
        ))

        assert value == 15_000.0

    def test_falls_back_to_configured_placeholder_when_nothing_available(self) -> None:
        scheduler = _make_scheduler(fallback_portfolio_value=42.0)
        scheduler._http.get = AsyncMock(return_value=_resp(json_body={"configured": False}))

        value = asyncio.run(scheduler._fetch_portfolio_value({}, {}))

        assert value == 42.0


class TestPlanExecution:
    def test_twap_style_uses_plan_twap(self) -> None:
        scheduler = _make_scheduler(execution_style="twap", twap_slices=4)
        instrs = [OrderInstruction(symbol="AAPL", side="buy", qty=40.0, target_weight=0.5, current_qty=0.0, estimated_value=4000.0)]

        plan = asyncio.run(scheduler._plan_execution(instrs))

        assert plan.total_orders == 4
        assert all(s.qty == 10.0 for s in plan.slices)

    def test_vwap_style_fetches_volume_and_weights_slices(self) -> None:
        scheduler = _make_scheduler(execution_style="vwap", twap_slices=2)
        instrs = [OrderInstruction(symbol="AAPL", side="buy", qty=100.0, target_weight=0.5, current_qty=0.0, estimated_value=10000.0)]
        scheduler._http.get = AsyncMock(return_value=_resp(json_body={
            "data": [{"bar_ts": 1700000000, "volume": 300}, {"bar_ts": 1700000900, "volume": 100}]
        }))

        plan = asyncio.run(scheduler._plan_execution(instrs))

        assert plan.total_orders == 2
        assert plan.slices[0].qty == 75.0
        assert plan.slices[1].qty == 25.0
