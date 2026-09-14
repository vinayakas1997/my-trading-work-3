import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from vinu_live.config import LiveConfig
from vinu_live.execution import ExecutionPlan, ExecutionSlice
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


class TestFetchPositions:
    """A broker-positions fetch failure must abort the cycle, not silently
    look like a flat book -- signal_translator.translate() uses this as the
    current-holdings baseline, so a fabricated {} would size a real existing
    position as a fresh entry (doubling up) or hide a needed exit entirely."""

    def test_returns_position_map_on_success(self) -> None:
        scheduler = _make_scheduler()
        scheduler._http.get = AsyncMock(return_value=_resp(json_body=[{"symbol": "AAPL", "qty": 10.0}]))

        positions = asyncio.run(scheduler._fetch_positions())

        assert positions == {"AAPL": 10.0}

    def test_raises_on_http_error_instead_of_returning_empty(self) -> None:
        scheduler = _make_scheduler()
        resp = _resp(status_code=500)
        resp.raise_for_status.side_effect = httpx.HTTPStatusError("500", request=MagicMock(), response=resp)
        scheduler._http.get = AsyncMock(return_value=resp)

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(scheduler._fetch_positions())

    def test_raises_on_connection_error_instead_of_returning_empty(self) -> None:
        scheduler = _make_scheduler()
        scheduler._http.get = AsyncMock(side_effect=ConnectionError("down"))

        with pytest.raises(ConnectionError):
            asyncio.run(scheduler._fetch_positions())

    def test_raises_on_unexpected_response_shape(self) -> None:
        scheduler = _make_scheduler()
        scheduler._http.get = AsyncMock(return_value=_resp(json_body={"not": "a list"}))

        with pytest.raises(ValueError):
            asyncio.run(scheduler._fetch_positions())

    def test_cycle_marks_failed_when_positions_fetch_fails(self) -> None:
        scheduler = _make_scheduler()

        async def _get(url, **kwargs):
            if "/portfolio/state" in url:
                return _resp(json_body={"weights": [{"symbol": "AAPL", "target_weight": 0.1}]})
            raise ConnectionError("positions down")

        scheduler._http.get = AsyncMock(side_effect=_get)

        result = asyncio.run(scheduler.cycle())

        assert result["status"] == "failed"


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


class TestExecutePlanGuards:
    """Execution unification follow-up: this path used to fire straight to
    the broker with no risk gates at all, unlike the signal-driven entry
    path's spread/event-blackout checks. Same guards now apply here too,
    per-slice, fail-open on any quote/calendar problem."""

    @staticmethod
    def _plan(symbol="AAPL", qty=10.0):
        return ExecutionPlan(slices=[ExecutionSlice(symbol=symbol, side="buy", qty=qty, slice_number=1, total_slices=1)])

    def test_wide_spread_skips_the_slice(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        scheduler = _make_scheduler()

        async def _get(url, params=None, **kwargs):
            if "/stock/quote" in url:
                return _resp(json_body={"ok": True, "spread_bps": 500.0})
            return _resp(status_code=404)

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp(json_body={"status": "submitted"}))

        submitted = asyncio.run(scheduler._execute_plan(self._plan()))

        assert submitted[0]["status"] == "skipped"
        assert scheduler._http.post.call_count == 0

    def test_event_blackout_skips_the_slice(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        scheduler = _make_scheduler()

        async def _get(url, params=None, **kwargs):
            if "/stock/events" in url:
                return _resp(json_body={"blackout": True, "events": [{"title": "CPI"}]})
            return _resp(status_code=404)

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp(json_body={"status": "submitted"}))

        submitted = asyncio.run(scheduler._execute_plan(self._plan()))

        assert submitted[0]["status"] == "skipped"
        assert submitted[0]["reason"] == "CPI"
        assert scheduler._http.post.call_count == 0

    def test_clean_quote_and_calendar_submits_normally(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        scheduler = _make_scheduler()
        scheduler._http.get = AsyncMock(return_value=_resp(status_code=404))
        scheduler._http.post = AsyncMock(return_value=_resp(json_body={"status": "submitted"}))

        submitted = asyncio.run(scheduler._execute_plan(self._plan()))

        assert submitted[0]["status"] == "submitted"
        assert scheduler._http.post.call_count == 1


class TestExecutePlanDynamicRouting:
    """Execution unification follow-up: this path used to hardcode
    order_type="market" regardless of spread, unlike the entry path's
    dynamic spread-based routing. Same _choose_entry_order_type decision
    now applies here too, with a price-aware fallback to market when a
    limit order type would have no usable price to place at."""

    @staticmethod
    def _plan(symbol="AAPL", side="buy", qty=10.0):
        return ExecutionPlan(slices=[ExecutionSlice(symbol=symbol, side=side, qty=qty, slice_number=1, total_slices=1)])

    def test_tight_spread_stays_market(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        scheduler = _make_scheduler()

        async def _get(url, params=None, **kwargs):
            if "/stock/quote" in url:
                return _resp(json_body={"ok": True, "spread_bps": 2.0})
            return _resp(status_code=404)

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp(json_body={"status": "submitted"}))

        asyncio.run(scheduler._execute_plan(self._plan(), prices={"AAPL": 150.0}))

        _, kwargs = scheduler._http.post.call_args
        assert kwargs["json"]["order_type"] == "market"
        assert "limit_price" not in kwargs["json"]

    def test_wide_spread_within_gate_routes_limit_with_price(self, tmp_path, monkeypatch) -> None:
        # 10bps: inside MAX_SPREAD_BPS (25, doesn't block) but over the
        # default ~5bps slippage-routing budget -- must go limit, not
        # market, with a price-derived limit_price attached.
        monkeypatch.setenv("HOME", str(tmp_path))
        scheduler = _make_scheduler()

        async def _get(url, params=None, **kwargs):
            if "/stock/quote" in url:
                return _resp(json_body={"ok": True, "spread_bps": 10.0})
            return _resp(status_code=404)

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp(json_body={"status": "submitted"}))

        asyncio.run(scheduler._execute_plan(self._plan(side="buy"), prices={"AAPL": 150.0}))

        _, kwargs = scheduler._http.post.call_args
        assert kwargs["json"]["order_type"] == "limit"
        assert kwargs["json"]["limit_price"] < 150.0  # passive side of a buy

    def test_limit_routing_without_a_known_price_falls_back_to_market(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        scheduler = _make_scheduler()

        async def _get(url, params=None, **kwargs):
            if "/stock/quote" in url:
                return _resp(json_body={"ok": True, "spread_bps": 10.0})
            return _resp(status_code=404)

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp(json_body={"status": "submitted"}))

        # No prices dict at all -- fail-open to market rather than guessing.
        asyncio.run(scheduler._execute_plan(self._plan()))

        _, kwargs = scheduler._http.post.call_args
        assert kwargs["json"]["order_type"] == "market"
        assert "limit_price" not in kwargs["json"]

    def test_no_quote_fails_open_to_market(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        scheduler = _make_scheduler()
        scheduler._http.get = AsyncMock(return_value=_resp(status_code=404))
        scheduler._http.post = AsyncMock(return_value=_resp(json_body={"status": "submitted"}))

        asyncio.run(scheduler._execute_plan(self._plan(), prices={"AAPL": 150.0}))

        _, kwargs = scheduler._http.post.call_args
        assert kwargs["json"]["order_type"] == "market"

    def test_per_instruction_slippage_budget_tightens_routing(self, tmp_path, monkeypatch) -> None:
        # A tight per-slice max_slippage_pct (0.0002 = 2bps) forces limit
        # routing at a spread (1.5bps) that's under its own tightened gate
        # ceiling (min(25, 2)=2bps, so it isn't skipped) but over its
        # routing budget (2bps * SLIPPAGE_BUDGET_FRACTION 0.5 = 1bps) --
        # a spread this tight would stay market under the wider ~5bps
        # global default budget.
        monkeypatch.setenv("HOME", str(tmp_path))
        scheduler = _make_scheduler()

        async def _get(url, params=None, **kwargs):
            if "/stock/quote" in url:
                return _resp(json_body={"ok": True, "spread_bps": 1.5})
            return _resp(status_code=404)

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp(json_body={"status": "submitted"}))
        tight_plan = ExecutionPlan(slices=[
            ExecutionSlice(symbol="AAPL", side="buy", qty=10.0, slice_number=1, total_slices=1, max_slippage_pct=0.0002),
        ])

        asyncio.run(scheduler._execute_plan(tight_plan, prices={"AAPL": 150.0}))

        _, kwargs = scheduler._http.post.call_args
        assert kwargs["json"]["order_type"] == "limit"
