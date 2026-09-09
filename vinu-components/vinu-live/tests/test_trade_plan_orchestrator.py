import asyncio
import json
import os
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.book.positions import init_book, list_open_positions, open_position
from vinu_live.book.quantize import qty_float
from vinu_live.breaker.engine import BreakerVerdict
from vinu_live.config import LiveConfig
from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator
from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue


@pytest.fixture
def book():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    be = init_book(db_path)
    yield be
    be.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def _make_orchestrator(book, **config_overrides) -> TradePlanOrchestrator:
    config = LiveConfig(**config_overrides)
    # In-memory, per-test-isolated -- config.data_root's real
    # rebalance_requests.db would otherwise be shared (and polluted)
    # across every test using this helper, since none of them override
    # data_root.
    orch = TradePlanOrchestrator(config, book=book, rebalance_queue=RebalanceRequestQueue(":memory:"))
    orch._http = MagicMock()
    return orch


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


_SAMPLE_PLAN = {
    "symbol": "AAPL",
    "timeframe": "daily",
    "direction": "long",
    "risk_bands": {"max_position_size_pct": 0.05, "volatility_band_upper": 0.3},
    "contingency_rules": [
        {"metric": "drawdown_pct", "operator": ">=", "threshold": 0.05,
         "action": "reduce_position", "action_params": {"reduce_by_pct": 0.5}},
    ],
    "invalidation_conditions": [
        {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.10,
         "action": "exit", "action_params": {}},
    ],
    "forecast": {"direction": "long", "confidence": 0.6, "magnitude_pct": 0.03, "magnitude_std": 0.02},
}


def _router(get_routes: dict, post_routes: dict | None = None):
    post_routes = post_routes or {}

    async def _get(url, params=None, **kwargs):
        for prefix, body in get_routes.items():
            if prefix in url:
                return _resp(json_body=body)
        return _resp(status_code=404)

    async def _post(url, json=None, **kwargs):
        for prefix, body in post_routes.items():
            if prefix in url:
                return _resp(json_body=body)
        return _resp(status_code=404)

    return AsyncMock(side_effect=_get), AsyncMock(side_effect=_post)


class TestFetchActiveTradePlans:
    def test_fetches_and_parses_plan_data(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router({
            "/research/artifacts": [{"artifact_id": "art_1", "status": "ACTIVE", "type": "trade_plan"}],
            "/research/trade-plan/art_1": {"artifact_id": "art_1", "trade_plan_data": json.dumps(_SAMPLE_PLAN)},
        })
        orch._http.get = get_mock

        plans = asyncio.run(orch._fetch_active_trade_plans())

        assert len(plans) == 1
        assert plans[0]["symbol"] == "AAPL"
        assert plans[0]["_artifact_id"] == "art_1"

    def test_no_active_plans_returns_empty(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, _ = _router({"/research/artifacts": []})
        orch._http.get = get_mock

        plans = asyncio.run(orch._fetch_active_trade_plans())
        assert plans == []

    def test_artifact_list_failure_returns_empty(self, book) -> None:
        orch = _make_orchestrator(book)
        orch._http.get = AsyncMock(side_effect=ConnectionError("down"))

        plans = asyncio.run(orch._fetch_active_trade_plans())
        assert plans == []


class TestEntry:
    def test_enters_position_when_flat_and_breaker_allows(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/candles/AAPL": {"data": [{"close": 150.0}]},
                "/broker/positions": [],
            },
            post_routes={
                "/broker/order": {"status": "submitted", "order_id": "o1"},
            },
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"
        positions = list_open_positions(book, symbol="AAPL")
        assert len(positions) == 1
        assert positions[0].side == "long"

    def test_neutral_direction_never_enters(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "direction": "neutral"}
        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))
        assert action is None
        assert list_open_positions(book) == []

    def test_zero_position_size_skips_entry(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "risk_bands": {"max_position_size_pct": 0.0}}
        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))
        assert action is None
        assert list_open_positions(book) == []

    def test_breaker_halt_blocks_entry(self, book) -> None:
        orch = _make_orchestrator(book)
        # Force the breaker into a halted state directly -- simplest way to exercise
        # the "no order path skips the breaker" guarantee without a real limit breach.
        orch._breaker_state.halted = True
        orch._breaker_state.halted_reason = "manual test halt"
        get_mock, post_mock = _router(get_routes={"/broker/positions": []})
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entry_blocked_by_breaker"
        assert post_mock.call_count == 0
        assert list_open_positions(book) == []

    def test_order_not_submitted_does_not_write_book(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "pending_confirmation"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entry_not_filled"
        assert list_open_positions(book) == []


class TestForecastConfidenceScalesEntrySize:
    """Stage 2 (how-to-make-it-live.md #24): TradePlan.forecast.confidence
    was computed but never read at the one place a TradePlan's actual entry
    size is decided. _SAMPLE_PLAN's own risk_bands.max_position_size_pct is
    0.05 -- at price 150 / portfolio 100000, that's qty 33.33 unscaled."""

    def test_high_confidence_uses_close_to_full_size(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "forecast": {"confidence": 0.95}}
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        qty = list_open_positions(book, symbol="AAPL")[0].qty
        assert qty == qty_float(0.05 * 0.95 * 100000.0 / 150.0)

    def test_low_confidence_shrinks_size_but_floors_at_half(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "forecast": {"confidence": 0.1}}
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        qty = list_open_positions(book, symbol="AAPL")[0].qty
        # floored at 0.5, not scaled all the way down to 0.1
        assert qty == qty_float(0.05 * 0.5 * 100000.0 / 150.0)

    def test_missing_forecast_uses_full_size(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {k: v for k, v in _SAMPLE_PLAN.items() if k != "forecast"}
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        qty = list_open_positions(book, symbol="AAPL")[0].qty
        assert qty == qty_float(0.05 * 100000.0 / 150.0)

    def test_disabled_via_env_uses_full_size(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "FORECAST_SCALING_ENABLED", False)
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "forecast": {"confidence": 0.1}}
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        qty = list_open_positions(book, symbol="AAPL")[0].qty
        assert qty == qty_float(0.05 * 100000.0 / 150.0)


class TestSignalAgeBlocksStaleEntry:
    """Stage 2 (how-to-make-it-live.md #9/#36): a TradePlan was "valid until
    invalidated," not "valid for a window" -- a several-day-old setup with
    no fill was still actionable forever. trade_plan_authoring.py already
    stamps created_at at generation time; this proves _maybe_enter now
    actually reads it."""

    @staticmethod
    def _iso_hours_ago(hours: float) -> str:
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    def test_fresh_signal_enters_normally(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "created_at": self._iso_hours_ago(1)}
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_stale_signal_blocks_entry(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "created_at": self._iso_hours_ago(100.0)}  # default max is 72h
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entry_blocked_by_stale_signal"
        assert post_mock.call_count == 0
        assert list_open_positions(book) == []

    def test_missing_created_at_never_blocks(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {k: v for k, v in _SAMPLE_PLAN.items() if k != "created_at"}
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_unparseable_created_at_never_blocks(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "created_at": "not-a-timestamp"}
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_disabled_via_env_never_blocks(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "SIGNAL_MAX_AGE_HOURS", 0.0)
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "created_at": self._iso_hours_ago(100000.0)}
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"


class TestCvarGateAndVolTargeting:
    """how-to-make-it-live.md #17: cvar_exceeds / vol_target_scale were built
    in vinu-agent but no live-path caller ever fed them data, so the
    VINU_RISK_CVAR_ENABLED / VINU_RISK_VOL_TARGET_ENABLED flags were inert.
    _maybe_enter now reads cvar_95_limit / daily_vol frozen onto RiskBand and
    applies both. Both gates default OFF, so these monkeypatch them on."""

    @staticmethod
    def _mocks():
        return _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )

    def test_cvar_above_threshold_blocks_entry(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "CVAR_GATE_ENABLED", True)
        monkeypatch.setattr(orch_mod, "CVAR_THRESHOLD", 0.03)
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "risk_bands": {"max_position_size_pct": 0.05, "cvar_95_limit": 0.05}}
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entry_blocked_by_cvar"
        assert post_mock.call_count == 0
        assert list_open_positions(book) == []

    def test_cvar_below_threshold_enters(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "CVAR_GATE_ENABLED", True)
        monkeypatch.setattr(orch_mod, "CVAR_THRESHOLD", 0.03)
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "risk_bands": {"max_position_size_pct": 0.05, "cvar_95_limit": 0.02}}
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_cvar_missing_never_blocks(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "CVAR_GATE_ENABLED", True)
        orch = _make_orchestrator(book)
        # _SAMPLE_PLAN's risk_bands has no cvar_95_limit -> 0.0 -> skipped
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_cvar_gate_disabled_ignores_fat_tail(self, book) -> None:
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "risk_bands": {"max_position_size_pct": 0.05, "cvar_95_limit": 0.9}}
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_high_vol_scales_size_down(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "VOL_TARGET_ENABLED", True)
        monkeypatch.setattr(orch_mod, "FORECAST_SCALING_ENABLED", False)
        monkeypatch.setattr(orch_mod, "VOL_TARGET", 0.15)
        orch = _make_orchestrator(book)
        # daily target = 0.15 / sqrt(252) ~= 0.009449; daily_vol 0.03 is ~3.17x
        # -> scale ~= 0.315
        plan = {**_SAMPLE_PLAN, "risk_bands": {"max_position_size_pct": 0.05, "daily_vol": 0.03}}
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        expected_scale = (0.15 / (252.0 ** 0.5)) / 0.03
        qty = list_open_positions(book, symbol="AAPL")[0].qty
        assert qty == qty_float(0.05 * expected_scale * 100000.0 / 150.0)

    def test_low_vol_does_not_scale_up(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "VOL_TARGET_ENABLED", True)
        monkeypatch.setattr(orch_mod, "FORECAST_SCALING_ENABLED", False)
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "risk_bands": {"max_position_size_pct": 0.05, "daily_vol": 0.001}}
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        qty = list_open_positions(book, symbol="AAPL")[0].qty
        assert qty == qty_float(0.05 * 100000.0 / 150.0)  # capped at 1.0x

    def test_vol_targeting_disabled_uses_full_size(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "FORECAST_SCALING_ENABLED", False)
        orch = _make_orchestrator(book)
        plan = {**_SAMPLE_PLAN, "risk_bands": {"max_position_size_pct": 0.05, "daily_vol": 0.03}}
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        asyncio.run(orch._maybe_enter(plan, "AAPL", 150.0, 100000.0))

        qty = list_open_positions(book, symbol="AAPL")[0].qty
        assert qty == qty_float(0.05 * 100000.0 / 150.0)


class TestDataFreshnessGuard:
    """how-to-make-it-live.md #16 (Stage 3): the live cycle fetches interval=1d
    candles; a stalled ingest feed just stops advancing the newest bar and
    every entry decision is then made on a stale mark. Pauses ENTRIES only
    (exits always proceed). Guard defaults ON at 96h."""

    @staticmethod
    def _mocks():
        return _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )

    @staticmethod
    def _epoch_hours_ago(hours: float) -> float:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).timestamp() - hours * 3600.0

    def test_fresh_data_enters_normally(self, book) -> None:
        orch = _make_orchestrator(book)
        orch._last_price_ts["AAPL"] = self._epoch_hours_ago(2)
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_stale_data_blocks_entry(self, book) -> None:
        orch = _make_orchestrator(book)
        orch._last_price_ts["AAPL"] = self._epoch_hours_ago(200)  # default max 96h
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entry_blocked_by_stale_data"
        assert post_mock.call_count == 0
        assert list_open_positions(book) == []

    def test_missing_timestamp_never_blocks(self, book) -> None:
        orch = _make_orchestrator(book)
        # no _last_price_ts entry for AAPL -> fail-open
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_disabled_via_env_never_blocks(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "PRICE_MAX_AGE_HOURS", 0.0)
        orch = _make_orchestrator(book)
        orch._last_price_ts["AAPL"] = self._epoch_hours_ago(10000)
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_stale_data_does_not_block_exit_evaluation(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._last_price_ts["AAPL"] = self._epoch_hours_ago(200)
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o2"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        # invalidation condition: unrealized_pnl_pct <= -0.10; price 130 on a
        # 150 long is -13.3% -> exit fires despite the stale feed.
        action = asyncio.run(
            orch._evaluate_open_position(_SAMPLE_PLAN, list_open_positions(book)[0], 130.0, 100000.0)
        )

        assert action["action"] == "invalidation_exit"
        assert list_open_positions(book, symbol="AAPL") == []

    def test_fetch_prices_populates_last_price_ts(self, book) -> None:
        orch = _make_orchestrator(book)
        recent = self._epoch_hours_ago(1)
        get_mock, _ = _router(get_routes={
            "/candles/AAPL": {"data": [{"close": 150.0, "bar_ts": recent}]},
        })
        orch._http.get = get_mock

        prices = asyncio.run(orch._fetch_prices(["AAPL"]))

        assert prices["AAPL"] == 150.0
        assert orch._last_price_ts["AAPL"] == recent

    def test_fetch_prices_clears_stale_ts_when_new_bar_has_none(self, book) -> None:
        orch = _make_orchestrator(book)
        orch._last_price_ts["AAPL"] = self._epoch_hours_ago(500)
        get_mock, _ = _router(get_routes={
            "/candles/AAPL": {"data": [{"close": 151.0}]},  # no bar_ts
        })
        orch._http.get = get_mock

        asyncio.run(orch._fetch_prices(["AAPL"]))

        assert "AAPL" not in orch._last_price_ts


def _entry_mocks_positions_seq(snapshots):
    """GET /broker/positions returns snapshots[0], [1], ... then repeats the
    last; POST /broker/order always 'submitted'. Used to model a flat account
    pre-submit and the broker's real fill afterwards."""
    calls = {"n": 0}

    async def _get(url, params=None, **kwargs):
        if "/broker/positions" in url:
            i = min(calls["n"], len(snapshots) - 1)
            calls["n"] += 1
            return _resp(json_body=snapshots[i])
        return _resp(status_code=404)

    async def _post(url, json=None, **kwargs):
        if "/broker/order" in url:
            return _resp(json_body={"status": "submitted", "order_id": "o1"})
        return _resp(status_code=404)

    return AsyncMock(side_effect=_get), AsyncMock(side_effect=_post)


class TestPartialFillHandling:
    """how-to-make-it-live.md #15 (Stage 3): the order path booked the INTENDED
    qty the instant the broker returned 'submitted', so a partial fill left
    every downstream calc keyed off shares the account never held. _maybe_enter
    now polls the broker's real position and books what actually filled;
    end-of-cycle reconciliation pulls the book to broker truth on any drift."""

    @staticmethod
    def _intended_qty() -> float:
        # _SAMPLE_PLAN: size_pct 0.05 * forecast.confidence 0.6 (scaling on)
        return qty_float(0.05 * 0.6 * 100000.0 / 150.0)

    def test_full_fill_books_intended(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "FILL_CONFIRM_DELAY_SEC", 0.0)
        orch = _make_orchestrator(book)
        intended = self._intended_qty()
        get_mock, post_mock = _entry_mocks_positions_seq(
            [[], [{"symbol": "AAPL", "qty": intended}]]  # flat pre, filled post
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"
        assert "partial_fill" not in action
        assert list_open_positions(book, symbol="AAPL")[0].qty == intended

    def test_partial_fill_books_actual(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "FILL_CONFIRM_DELAY_SEC", 0.0)
        orch = _make_orchestrator(book)
        intended = self._intended_qty()
        get_mock, post_mock = _entry_mocks_positions_seq(
            [[], [{"symbol": "AAPL", "qty": 5.0}]]  # only 5 of ~33 filled
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"
        assert action["partial_fill"] is True
        assert action["intended_qty"] == intended
        assert action["qty"] == qty_float(5.0)
        assert list_open_positions(book, symbol="AAPL")[0].qty == qty_float(5.0)

    def test_broker_unavailable_falls_back_to_intended(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "FILL_CONFIRM_DELAY_SEC", 0.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _entry_mocks_positions_seq([[]])  # always empty
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"
        assert "partial_fill" not in action
        assert list_open_positions(book, symbol="AAPL")[0].qty == self._intended_qty()

    def test_async_fill_lag_falls_back_to_intended(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "FILL_CONFIRM_DELAY_SEC", 0.0)
        orch = _make_orchestrator(book)
        # broker responds, but our symbol isn't visible yet (fill still settling)
        get_mock, post_mock = _entry_mocks_positions_seq([[], [{"symbol": "MSFT", "qty": 3.0}]])
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"
        assert "partial_fill" not in action
        assert list_open_positions(book, symbol="AAPL")[0].qty == self._intended_qty()

    # --- reconciliation self-heal ---

    def test_reconcile_reduces_book_to_broker(self, book) -> None:
        open_position(book, "AAPL", "long", 100.0, 150.0)
        orch = _make_orchestrator(book)
        orch._http.get = _router({"/broker/positions": [{"symbol": "AAPL", "qty": 40.0}]})[0]

        recon = asyncio.run(orch._reconcile_book_with_broker({"AAPL": 150.0}))

        assert recon["drift_detected"] is True
        assert recon["corrections"][0]["action"] == "reduced_to_match_broker"
        assert list_open_positions(book, symbol="AAPL")[0].qty == qty_float(40.0)

    def test_reconcile_closes_book_when_broker_flat_on_that_symbol(self, book) -> None:
        open_position(book, "AAPL", "long", 100.0, 150.0)
        open_position(book, "MSFT", "long", 10.0, 300.0)
        orch = _make_orchestrator(book)
        # broker snapshot non-empty (MSFT present) but AAPL gone
        orch._http.get = _router({"/broker/positions": [{"symbol": "MSFT", "qty": 10.0}]})[0]

        recon = asyncio.run(orch._reconcile_book_with_broker({"AAPL": 150.0, "MSFT": 300.0}))

        actions = {c["symbol"]: c["action"] for c in recon["corrections"]}
        assert actions["AAPL"] == "closed_to_match_broker"
        assert list_open_positions(book, symbol="AAPL") == []
        assert len(list_open_positions(book, symbol="MSFT")) == 1

    def test_reconcile_skips_when_broker_snapshot_empty(self, book) -> None:
        open_position(book, "AAPL", "long", 100.0, 150.0)
        orch = _make_orchestrator(book)
        orch._http.get = _router({"/broker/positions": []})[0]

        recon = asyncio.run(orch._reconcile_book_with_broker({"AAPL": 150.0}))

        # drift is detected (book 100 vs broker 0) but NOT auto-corrected --
        # an empty snapshot can't be told apart from a failed fetch.
        assert recon["drift_detected"] is True
        assert recon["corrections"] == []
        assert list_open_positions(book, symbol="AAPL")[0].qty == qty_float(100.0)

    def test_reconcile_alerts_on_side_conflict_no_change(self, book) -> None:
        open_position(book, "AAPL", "long", 100.0, 150.0)
        orch = _make_orchestrator(book)
        orch._http.get = _router({"/broker/positions": [{"symbol": "AAPL", "qty": -50.0}]})[0]

        recon = asyncio.run(orch._reconcile_book_with_broker({"AAPL": 150.0}))

        assert recon["corrections"][0]["action"] == "alert_side_conflict"
        assert list_open_positions(book, symbol="AAPL")[0].qty == qty_float(100.0)

    def test_reconcile_alerts_on_phantom_broker_position(self, book) -> None:
        open_position(book, "AAPL", "long", 100.0, 150.0)
        orch = _make_orchestrator(book)
        orch._http.get = _router(
            {"/broker/positions": [{"symbol": "AAPL", "qty": 100.0}, {"symbol": "TSLA", "qty": 7.0}]}
        )[0]

        recon = asyncio.run(orch._reconcile_book_with_broker({"AAPL": 150.0, "TSLA": 200.0}))

        actions = {c["symbol"]: c["action"] for c in recon["corrections"]}
        assert actions["TSLA"] == "alert_phantom_broker_position"

    def test_reconcile_autocorrect_disabled_warns_only(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "RECONCILE_AUTOCORRECT", False)
        open_position(book, "AAPL", "long", 100.0, 150.0)
        orch = _make_orchestrator(book)
        orch._http.get = _router({"/broker/positions": [{"symbol": "AAPL", "qty": 40.0}]})[0]

        recon = asyncio.run(orch._reconcile_book_with_broker({"AAPL": 150.0}))

        assert recon["drift_detected"] is True
        assert recon["corrections"] == []
        assert list_open_positions(book, symbol="AAPL")[0].qty == qty_float(100.0)


class TestRuntimeCorrelationMonitor:
    """how-to-make-it-live.md #12 (Stage 3): the DCC/shrinkage covariance was
    only used by the breaker's aggregate-VaR check -- nothing trimmed two open
    positions that started moving together. _check_runtime_correlation now
    reduce_only-shrinks the larger side of a dangerously co-moving pair."""

    @staticmethod
    def _cov(rho: float, v: float = 1.0):
        import numpy as np
        return np.array([[v, rho * v], [rho * v, v]])

    @staticmethod
    def _order_mock():
        _, post = _router(get_routes={}, post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}})
        return post

    def test_reduces_larger_of_correlated_same_direction_pair(self, book) -> None:
        open_position(book, "AAA", "long", 100.0, 10.0)   # mv 1000 -> the larger
        open_position(book, "BBB", "long", 50.0, 10.0)    # mv 500
        orch = _make_orchestrator(book)
        orch._compute_covariance = AsyncMock(return_value=self._cov(0.95))
        orch._http.post = self._order_mock()

        res = asyncio.run(orch._check_runtime_correlation({"AAA": 10.0, "BBB": 10.0}))

        assert res["checked"] is True
        assert res["n_flagged_pairs"] == 1
        assert res["reductions"][0]["symbol"] == "AAA"
        assert list_open_positions(book, symbol="AAA")[0].qty == qty_float(75.0)  # -25%
        assert list_open_positions(book, symbol="BBB")[0].qty == qty_float(50.0)  # untouched

    def test_opposite_direction_pair_is_a_hedge_not_flagged(self, book) -> None:
        open_position(book, "AAA", "long", 100.0, 10.0)
        open_position(book, "BBB", "short", 100.0, 10.0)
        orch = _make_orchestrator(book)
        orch._compute_covariance = AsyncMock(return_value=self._cov(0.95))
        orch._http.post = self._order_mock()

        res = asyncio.run(orch._check_runtime_correlation({"AAA": 10.0, "BBB": 10.0}))

        assert res["n_flagged_pairs"] == 0
        assert res["reductions"] == []
        assert list_open_positions(book, symbol="AAA")[0].qty == qty_float(100.0)

    def test_correlation_below_threshold_no_reduction(self, book) -> None:
        open_position(book, "AAA", "long", 100.0, 10.0)
        open_position(book, "BBB", "long", 100.0, 10.0)
        orch = _make_orchestrator(book)
        orch._compute_covariance = AsyncMock(return_value=self._cov(0.5))
        orch._http.post = self._order_mock()

        res = asyncio.run(orch._check_runtime_correlation({"AAA": 10.0, "BBB": 10.0}))

        assert res["n_flagged_pairs"] == 0
        assert list_open_positions(book, symbol="AAA")[0].qty == qty_float(100.0)

    def test_disabled_via_env(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "RUNTIME_CORR_ENABLED", False)
        open_position(book, "AAA", "long", 100.0, 10.0)
        open_position(book, "BBB", "long", 100.0, 10.0)
        orch = _make_orchestrator(book)
        orch._compute_covariance = AsyncMock(return_value=self._cov(0.99))

        res = asyncio.run(orch._check_runtime_correlation({"AAA": 10.0, "BBB": 10.0}))

        assert res["checked"] is False
        assert list_open_positions(book, symbol="AAA")[0].qty == qty_float(100.0)

    def test_fewer_than_two_symbols_no_op(self, book) -> None:
        open_position(book, "AAA", "long", 100.0, 10.0)
        orch = _make_orchestrator(book)
        res = asyncio.run(orch._check_runtime_correlation({"AAA": 10.0}))
        assert res["checked"] is False

    def test_covariance_unavailable_no_op(self, book) -> None:
        open_position(book, "AAA", "long", 100.0, 10.0)
        open_position(book, "BBB", "long", 100.0, 10.0)
        orch = _make_orchestrator(book)
        orch._compute_covariance = AsyncMock(return_value=None)
        res = asyncio.run(orch._check_runtime_correlation({"AAA": 10.0, "BBB": 10.0}))
        assert res["checked"] is False
        assert res["reason"] == "covariance unavailable"

    def test_per_symbol_cooldown_blocks_second_trim(self, book) -> None:
        open_position(book, "AAA", "long", 100.0, 10.0)
        open_position(book, "BBB", "long", 50.0, 10.0)
        orch = _make_orchestrator(book)
        orch._compute_covariance = AsyncMock(return_value=self._cov(0.95))
        orch._http.post = self._order_mock()

        first = asyncio.run(orch._check_runtime_correlation({"AAA": 10.0, "BBB": 10.0}))
        second = asyncio.run(orch._check_runtime_correlation({"AAA": 10.0, "BBB": 10.0}))

        assert first["reductions"][0]["symbol"] == "AAA"
        assert second["n_flagged_pairs"] == 1        # still flagged
        assert second["reductions"] == []            # but cooled down, no trim
        assert list_open_positions(book, symbol="AAA")[0].qty == qty_float(75.0)


class TestSignalConflictDetection:
    """how-to-make-it-live.md #3/#5 (Stage 3): more than one ACTIVE plan can
    name a symbol; nothing checked they agreed. _maybe_enter now refuses to
    open into a symbol another ACTIVE plan currently signals the opposite way."""

    @staticmethod
    def _mocks():
        return _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )

    def _long_plan(self):
        return {**_SAMPLE_PLAN, "direction": "long", "_artifact_id": "art_long"}

    def test_opposing_active_plan_blocks_entry(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock
        me = self._long_plan()
        others = [me, {**_SAMPLE_PLAN, "symbol": "AAPL", "direction": "short", "_artifact_id": "art_short"}]

        action = asyncio.run(orch._maybe_enter(me, "AAPL", 150.0, 100000.0, all_plans=others))

        assert action["action"] == "entry_blocked_by_signal_conflict"
        assert post_mock.call_count == 0
        assert list_open_positions(book) == []

    def test_agreeing_active_plans_enter_normally(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock
        me = self._long_plan()
        others = [me, {**_SAMPLE_PLAN, "symbol": "AAPL", "direction": "long", "_artifact_id": "art_long2"}]

        action = asyncio.run(orch._maybe_enter(me, "AAPL", 150.0, 100000.0, all_plans=others))

        assert action["action"] == "entered"

    def test_opposing_plan_on_other_symbol_is_not_a_conflict(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock
        me = self._long_plan()
        others = [me, {**_SAMPLE_PLAN, "symbol": "MSFT", "direction": "short", "_artifact_id": "art_msft"}]

        action = asyncio.run(orch._maybe_enter(me, "AAPL", 150.0, 100000.0, all_plans=others))

        assert action["action"] == "entered"

    def test_no_all_plans_arg_keeps_old_behavior(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(self._long_plan(), "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_policy_ignore_enters_despite_conflict(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "SIGNAL_CONFLICT_POLICY", "ignore")
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock
        me = self._long_plan()
        others = [me, {**_SAMPLE_PLAN, "symbol": "AAPL", "direction": "short", "_artifact_id": "art_short"}]

        action = asyncio.run(orch._maybe_enter(me, "AAPL", 150.0, 100000.0, all_plans=others))

        assert action["action"] == "entered"


class TestSpreadGate:
    """how-to-make-it-live.md #13 (Stage 4): liquidity / spread gate. _maybe_enter
    now fetches the live NBBO from vinu-stock-price at order time and refuses to
    open when the bid/ask spread (bps) is wider than VINU_LIVE_MAX_SPREAD_BPS.
    Entries only; fail-open on any quote problem. Default ceiling is 25 bps."""

    @staticmethod
    def _mocks(quote_body):
        get_routes = {"/broker/positions": []}
        if quote_body is not None:
            get_routes["/stock/quote"] = quote_body
        return _router(
            get_routes=get_routes,
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )

    @staticmethod
    def _quote(spread_bps, ok=True):
        mid = 150.0
        half = mid * (spread_bps / 10_000.0) / 2.0
        return {
            "symbol": "AAPL", "ok": ok, "bid": mid - half, "ask": mid + half,
            "mid": mid, "spread_bps": spread_bps, "ts": 0.0, "error": "",
        }

    def test_wide_spread_blocks_entry(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(self._quote(60.0))
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entry_blocked_by_wide_spread"
        assert post_mock.call_count == 0
        assert list_open_positions(book) == []

    def test_tight_spread_enters(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(self._quote(4.0))
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_quote_not_ok_fails_open(self, book) -> None:
        orch = _make_orchestrator(book)
        # ok:false with a nonsense spread -- the guard must ignore it entirely
        get_mock, post_mock = self._mocks(self._quote(9999.0, ok=False))
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_quote_route_unavailable_fails_open(self, book) -> None:
        orch = _make_orchestrator(book)
        # no /stock/quote route mocked -> _router returns 404 -> fail open
        get_mock, post_mock = self._mocks(None)
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_disabled_via_env_ignores_wide_spread(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "MAX_SPREAD_BPS", 0.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(self._quote(500.0))
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entered"

    def test_exit_is_never_gated_by_spread(self, book) -> None:
        # An open position being evaluated must never consult the spread gate --
        # _evaluate_open_position has no MAX_SPREAD_BPS branch at all. Prove a
        # pathologically wide quote does not stop an invalidation exit.
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
                "/stock/quote": self._quote(5000.0),
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o2"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        # 130 vs 150 entry = -13.3% unrealized -> past the -10% invalidation rule
        action = asyncio.run(
            orch._evaluate_open_position(_SAMPLE_PLAN, position, 130.0, 100000.0)
        )

        assert action["action"] == "invalidation_exit"
        assert list_open_positions(book, symbol="AAPL") == []


class TestBrokerOutagePause:
    """how-to-make-it-live.md #14 Half A (Stage 4): once per cycle the
    orchestrator probes /agent/broker/account. While that probe is failing
    (and past the grace window, or never confirmed since start) new ENTRIES
    pause with entry_blocked_by_broker_outage; exits are never gated; the
    flag auto-clears on the next healthy probe. BROKER_STALE_SEC=0 disables."""

    @staticmethod
    def _mocks(account_body):
        get_routes = {"/broker/positions": []}
        if account_body is not None:
            get_routes["/broker/account"] = account_body
        return _router(
            get_routes=get_routes,
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )

    def test_failed_probe_marks_degraded_and_blocks_entry(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(None)  # no /broker/account route -> 404
        orch._http.get, orch._http.post = get_mock, post_mock

        health = asyncio.run(orch._check_broker_health())
        assert health["degraded"] is True
        assert orch._broker_degraded is True

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))
        assert action["action"] == "entry_blocked_by_broker_outage"
        assert post_mock.call_count == 0
        assert list_open_positions(book) == []

    def test_healthy_probe_allows_entry(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks({"configured": True, "equity": 100000.0})
        orch._http.get, orch._http.post = get_mock, post_mock

        health = asyncio.run(orch._check_broker_health())
        assert health["degraded"] is False
        assert orch._broker_degraded is False

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))
        assert action["action"] == "entered"

    def test_recovery_clears_degraded_and_resumes_entries(self, book) -> None:
        orch = _make_orchestrator(book)
        orch._broker_degraded = True  # as if a prior cycle paused
        orch._broker_ok_at = 0.0
        get_mock, post_mock = self._mocks({"configured": True, "equity": 100000.0})
        orch._http.get, orch._http.post = get_mock, post_mock

        health = asyncio.run(orch._check_broker_health())
        assert health["degraded"] is False
        assert orch._broker_degraded is False

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))
        assert action["action"] == "entered"

    def test_exit_never_gated_while_broker_degraded(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._broker_degraded = True
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o2"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        # -13.3% vs the -10% invalidation rule -> exit fires despite degraded broker
        action = asyncio.run(
            orch._evaluate_open_position(_SAMPLE_PLAN, position, 130.0, 100000.0)
        )
        assert action["action"] == "invalidation_exit"
        assert list_open_positions(book, symbol="AAPL") == []

    def test_transient_blip_within_grace_does_not_pause(self, book) -> None:
        orch = _make_orchestrator(book)
        orch._broker_ok_at = time.monotonic()  # just confirmed healthy
        get_mock, post_mock = self._mocks(None)  # probe now fails
        orch._http.get, orch._http.post = get_mock, post_mock

        health = asyncio.run(orch._check_broker_health())
        assert health["degraded"] is False
        assert health.get("within_grace") is True
        assert orch._broker_degraded is False

    def test_disabled_via_env_ignores_degraded_flag(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "BROKER_STALE_SEC", 0.0)
        orch = _make_orchestrator(book)
        orch._broker_degraded = True  # stuck flag from before it was disabled
        get_mock, post_mock = self._mocks(None)
        orch._http.get, orch._http.post = get_mock, post_mock

        health = asyncio.run(orch._check_broker_health())
        assert health["enabled"] is False
        assert orch._broker_degraded is False  # disable clears it

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))
        assert action["action"] == "entered"

    def test_cycle_populates_broker_health(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/research/artifacts": [{"artifact_id": "art_1", "status": "ACTIVE", "type": "trade_plan"}],
                "/research/trade-plan/art_1": {"artifact_id": "art_1", "trade_plan_data": json.dumps(_SAMPLE_PLAN)},
                "/candles/AAPL": {"data": [{"close": 150.0}]},
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())
        assert result["broker_health"]["degraded"] is False
        assert result["actions"][0]["action"] == "entered"


class TestEmergencyFlatten:
    """how-to-make-it-live.md #33 (Stage 4): the panic switch. emergency_flatten()
    sets the agent's global kill switch AND reduce_only-closes every open book
    position; emergency_resume() lifts it; _maybe_enter refuses entries while
    self._trading_halted (mirror of the kill switch, refreshed each cycle)."""

    @staticmethod
    def _mocks(order_status="submitted", halt_ok=True, resume_ok=True, halted_status=False):
        get_routes = {
            "/broker/positions": [],
            "/broker/status": {"halted": halted_status},
            "/candles/": {"data": [{"close": 100.0}]},
        }
        post_routes = {"/broker/order": {"status": order_status}}
        if halt_ok:
            post_routes["/broker/halt"] = {"status": "ok", "halted": True}
        if resume_ok:
            post_routes["/broker/resume"] = {"status": "ok", "halted": False}
        get_mock, post_mock = _router(get_routes, post_routes)
        return get_mock, post_mock

    def test_flatten_halts_and_closes_all_positions(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0, artifact_id="a1")
        open_position(book, "MSFT", "short", 5.0, 300.0, artifact_id="a2")
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.emergency_flatten(reason="test panic"))

        assert result["status"] == "ok"
        assert result["halted"] is True
        assert result["count_closed"] == 2
        assert result["count_failed"] == 0
        assert list_open_positions(book) == []
        assert orch._trading_halted is True
        # one /broker/halt + one /broker/order per position
        halt_calls = [c for c in post_mock.call_args_list if "/broker/halt" in c.args[0]]
        order_calls = [c for c in post_mock.call_args_list if "/broker/order" in c.args[0]]
        assert len(halt_calls) == 1
        assert len(order_calls) == 2

    def test_flatten_reports_positions_that_did_not_close(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0, artifact_id="a1")
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(order_status="pending_confirmation")
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.emergency_flatten())

        assert result["status"] == "partial"
        assert result["count_closed"] == 0
        assert result["count_failed"] == 1
        assert result["positions_failed"][0]["symbol"] == "AAPL"
        # not closed => still in the book for reconciliation to catch
        assert len(list_open_positions(book)) == 1

    def test_flatten_still_closes_when_halt_endpoint_fails(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0, artifact_id="a1")
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(halt_ok=False)  # /broker/halt -> 404
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.emergency_flatten())

        assert result["halted"] is False
        assert result["halt_error"]
        assert result["status"] == "partial"
        assert result["count_closed"] == 1  # positions still flattened
        assert list_open_positions(book) == []

    def test_halted_flag_blocks_new_entries(self, book) -> None:
        orch = _make_orchestrator(book)
        orch._trading_halted = True
        get_mock, post_mock = _router(
            get_routes={"/broker/positions": []},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entry_blocked_by_emergency_halt"
        assert post_mock.call_count == 0
        assert list_open_positions(book) == []

    def test_is_trading_halted_reads_agent_status(self, book) -> None:
        orch = _make_orchestrator(book)
        get_true, _ = _router({"/broker/status": {"halted": True}})
        orch._http.get = get_true
        assert asyncio.run(orch._is_trading_halted()) is True

        get_down, _ = _router({"/broker/positions": []})  # no /broker/status -> 404
        orch._http.get = get_down
        assert asyncio.run(orch._is_trading_halted()) is False  # fail-safe = not halted

    def test_resume_lifts_the_halt(self, book) -> None:
        orch = _make_orchestrator(book)
        orch._trading_halted = True
        orch._breaker_state.halted = True
        get_mock, post_mock = self._mocks()
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.emergency_resume(reason="all clear"))

        assert result["resumed"] is True
        assert orch._trading_halted is False
        assert orch._breaker_state.halted is False

    def test_emergency_status_reports_state(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0, artifact_id="a1")
        orch = _make_orchestrator(book)
        get_mock, _ = _router({"/broker/status": {"halted": True}})
        orch._http.get = get_mock

        result = asyncio.run(orch.emergency_status())

        assert result["halted"] is True
        assert result["open_positions"] == 1

    def test_cycle_blocks_entry_when_agent_reports_halt(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/research/artifacts": [{"artifact_id": "art_1", "status": "ACTIVE", "type": "trade_plan"}],
                "/research/trade-plan/art_1": {"artifact_id": "art_1", "trade_plan_data": json.dumps(_SAMPLE_PLAN)},
                "/candles/AAPL": {"data": [{"close": 150.0}]},
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/broker/status": {"halted": True},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())

        assert result["trading_halted"] is True
        assert result["actions"][0]["action"] == "entry_blocked_by_emergency_halt"
        assert list_open_positions(book) == []


class TestEventBlackoutGuard:
    """how-to-make-it-live.md #2 (Stage 4): vinu-stock-price keeps a local
    earnings + US-macro calendar; _maybe_enter asks /stock/events/{symbol}
    and refuses a new entry when an event falls inside EVENT_BLACKOUT_HOURS.
    Entries only; fail-open on any calendar problem. Default window 24h."""

    @staticmethod
    def _mocks(events_body):
        get_routes = {"/broker/positions": []}
        if events_body is not None:
            get_routes["/stock/events"] = events_body
        return _router(
            get_routes=get_routes,
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )

    @staticmethod
    def _blackout(title="AAPL earnings (amc)"):
        return {"symbol": "AAPL", "within_hours": 24, "blackout": True,
                "events": [{"kind": "earnings", "title": title, "severity": 2}],
                "configured": True}

    @staticmethod
    def _clear():
        return {"symbol": "AAPL", "within_hours": 24, "blackout": False,
                "events": [], "configured": True}

    def test_event_in_window_blocks_entry(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(self._blackout())
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))

        assert action["action"] == "entry_blocked_by_event_blackout"
        assert action["reason"] == "AAPL earnings (amc)"
        assert post_mock.call_count == 0
        assert list_open_positions(book) == []

    def test_no_event_enters(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(self._clear())
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))
        assert action["action"] == "entered"

    def test_calendar_unavailable_fails_open(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(None)  # no /stock/events route -> 404
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))
        assert action["action"] == "entered"

    def test_blackout_true_without_events_list_still_blocks(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(
            {"symbol": "AAPL", "blackout": True, "configured": True}
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))
        assert action["action"] == "entry_blocked_by_event_blackout"
        assert action["reason"] == "event within blackout window"

    def test_disabled_via_env_ignores_blackout(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as m
        monkeypatch.setattr(m, "EVENT_BLACKOUT_HOURS", 0.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = self._mocks(self._blackout())
        orch._http.get, orch._http.post = get_mock, post_mock

        action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))
        assert action["action"] == "entered"

    def test_exit_is_never_gated_by_blackout(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
                "/stock/events": self._blackout(),
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o2"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        action = asyncio.run(
            orch._evaluate_open_position(_SAMPLE_PLAN, position, 130.0, 100000.0)
        )
        assert action["action"] == "invalidation_exit"
        assert list_open_positions(book, symbol="AAPL") == []


class TestEvaluateOpenPosition:
    def test_invalidation_triggers_exit(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o2"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 130.0, 100000.0))

        assert action["action"] == "invalidation_exit"
        assert list_open_positions(book, symbol="AAPL") == []

    def test_contingency_triggers_reduce(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o3"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        # 5% drawdown from 150 entry -> 142.5, matches the sample plan's contingency
        # rule (drawdown_pct >= 0.05) but not its invalidation rule (pnl <= -10%).
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 142.5, 100000.0))

        assert action["action"] == "reduce_position"
        remaining = list_open_positions(book, symbol="AAPL")[0]
        assert remaining.qty == pytest.approx(5.0)

    def test_no_rule_triggered_holds_and_logs(self, book, caplog) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
            },
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        with caplog.at_level("INFO"):
            action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 151.0, 100000.0))

        assert action["action"] == "hold"
        assert "No rule triggered" in caplog.text

    def test_breaker_halt_blocks_invalidation_exit(self, book, monkeypatch) -> None:
        # Old policy all = block exit (rollback). New default entries_only = allow exit.
        import vinu_live.trade_plan.orchestrator as _orch_mod
        monkeypatch.setattr(_orch_mod, "HALT_POLICY", "all")
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._breaker_state.halted = True
        orch._breaker_state.halted_reason = "manual test halt"
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 130.0, 100000.0))

        assert action["action"] == "exit_blocked_by_breaker"
        assert post_mock.call_count == 0
        assert list_open_positions(book, symbol="AAPL")[0].qty == 10.0

    def test_breaker_halt_entries_only_allows_exit(self, book, monkeypatch) -> None:
        import vinu_live.trade_plan.orchestrator as _orch_mod
        monkeypatch.setattr(_orch_mod, "HALT_POLICY", "entries_only")
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._breaker_state.halted = True
        orch._breaker_state.halted_reason = "manual test halt"
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 130.0, 100000.0))

        assert action["action"] in ("invalidation_exit", "exit_not_filled")
        # Risk-reducing exit attempted even on HALT entries-only.


class TestRebalanceRequestIntake:
    """Phase 5 (New-talk-agents/new-thinking/new-restructure/phases/
    phase-5-monitor-extend/): a rebalance request is advisory input only,
    evaluated after (never before) the plan's own real invalidation/
    contingency rules, and can be declined."""

    def test_invalidation_still_takes_priority_over_a_pending_request(self, book) -> None:
        """A rebalance request pending for the same symbol must never
        preempt a real invalidation exit -- proves the fold-in happens
        strictly after the existing rules, not instead of them."""
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._rebalance_queue.submit("AAPL", "free capital for candidate Y")
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o4"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 130.0, 100000.0))

        assert action["action"] == "invalidation_exit"  # not rebalance_*

    def test_rebalance_request_can_be_declined_by_orchestrator(self, book) -> None:
        """No invalidation/contingency reason to act, but a real
        unrealized gain protects the position -- the request is declined,
        not force-executed."""
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._rebalance_queue.submit("AAPL", "free capital for candidate Y")
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        # 160 vs. entry 150 = +6.67%, above the protect-gain threshold (5%),
        # and below both the plan's invalidation/contingency triggers.
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 160.0, 100000.0))

        assert action["action"] == "rebalance_declined"
        assert post_mock.call_count == 0  # no order submitted
        assert list_open_positions(book, symbol="AAPL")[0].qty == 10.0  # unchanged

    def test_rebalance_request_honored_when_no_protective_gain(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._rebalance_queue.submit("AAPL", "free capital for candidate Y")
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o5"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        # 151 vs. entry 150 = +0.67%, well under the protect-gain threshold.
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 151.0, 100000.0))

        assert action["action"] == "rebalance_honored"
        remaining = list_open_positions(book, symbol="AAPL")[0]
        assert remaining.qty == pytest.approx(5.0)  # reduced by half

    def test_critical_rebalance_request_overrides_gain_protect(self, book) -> None:
        """how-to-make-it-live.md #23: a critical request goes through even
        with an unrealized gain that would normally protect the position."""
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._rebalance_queue.submit("AAPL", "urgent: fund a better candidate", critical=True)
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o9"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        # +6.67% -- would be rebalance_declined for a non-critical request.
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 160.0, 100000.0))

        assert action["action"] == "rebalance_honored"
        assert action["critical"] is True
        assert list_open_positions(book, symbol="AAPL")[0].qty == pytest.approx(5.0)

    def test_rebalance_queue_round_trips_critical_flag(self, book) -> None:
        q = RebalanceRequestQueue(":memory:")
        q.submit("AAPL", "normal")
        assert q.pending_for("AAPL").critical is False
        q.submit("MSFT", "urgent", critical=True)
        assert q.pending_for("MSFT").critical is True

    def test_rebalance_request_blocked_by_breaker(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._breaker_state.halted = True
        orch._breaker_state.halted_reason = "manual test halt"
        orch._rebalance_queue.submit("AAPL", "free capital for candidate Y")
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 151.0, 100000.0))

        assert action["action"] == "rebalance_blocked_by_breaker"
        assert post_mock.call_count == 0

    def test_request_consumed_after_one_evaluation_not_reevaluated_every_cycle(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        orch._rebalance_queue.submit("AAPL", "free capital for candidate Y")
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/positions": [],
            },
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 160.0, 100000.0))
        assert orch._rebalance_queue.pending_for("AAPL") is None

        # A second evaluation with nothing re-submitted holds normally,
        # not re-declining the same (now-gone) request.
        action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 160.0, 100000.0))
        assert action["action"] == "hold"

    def test_no_pending_request_behaves_exactly_as_before(self, book, caplog) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": {"data": []},
                "/angle/shock_clustering/AAPL": {"data": []},
            },
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        position = list_open_positions(book, symbol="AAPL")[0]
        with caplog.at_level("INFO"):
            action = asyncio.run(orch._evaluate_open_position(_SAMPLE_PLAN, position, 151.0, 100000.0))

        assert action["action"] == "hold"
        assert "No rule triggered" in caplog.text


class TestShockTrigger:
    """Phase 5 (New-talk-agents/new-thinking/new-restructure/phases/
    phase-5-monitor-extend/): an off-cycle check invoked when a shock
    angle fires, using the exact same per-symbol evaluation as a normal
    cycle -- not a separate decision path."""

    _GET_ROUTES = {
        "/research/artifacts": [{"artifact_id": "art_1", "status": "ACTIVE", "type": "trade_plan"}],
        "/research/trade-plan/art_1": {"artifact_id": "art_1", "trade_plan_data": json.dumps(_SAMPLE_PLAN)},
        "/candles/AAPL": {"data": [{"close": 151.0}]},
        "/angle/shock_clustering/AAPL": {"data": []},
        "/broker/account": {"configured": True, "equity": 100000.0},
        "/broker/positions": [],
    }

    def test_shock_trigger_fires_off_cycle_check_for_open_position(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(self._GET_ROUTES)
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch.on_shock_event("aapl"))  # lowercase in, uppercase convention out

        assert action is not None
        assert action["action"] == "hold"  # +0.67%, no rule triggered
        assert action["symbol"] == "AAPL"

    def test_shock_trigger_can_enter_a_new_position(self, book) -> None:
        """No open position yet -- the off-cycle check still runs the
        same real entry logic a normal cycle would."""
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            self._GET_ROUTES,
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o6"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch.on_shock_event("AAPL"))

        assert action["action"] == "entered"
        assert len(list_open_positions(book, symbol="AAPL")) == 1

    def test_shock_trigger_debounced_within_window(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(self._GET_ROUTES)
        orch._http.get = get_mock
        orch._http.post = post_mock

        first = asyncio.run(orch.on_shock_event("AAPL"))
        assert first is not None
        calls_after_first = get_mock.call_count

        # 4 more shock events in immediate succession -- same debounce
        # window, must not trigger 4 more real evaluations.
        for _ in range(4):
            result = asyncio.run(orch.on_shock_event("AAPL"))
            assert result is None

        assert get_mock.call_count == calls_after_first  # no new fetches at all

    def test_shock_trigger_fires_again_after_debounce_window_elapses(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(self._GET_ROUTES)
        orch._http.get = get_mock
        orch._http.post = post_mock

        asyncio.run(orch.on_shock_event("AAPL"))
        orch._last_shock_trigger["AAPL"] -= orch._SHOCK_DEBOUNCE_SEC + 1  # simulate elapsed time

        second = asyncio.run(orch.on_shock_event("AAPL"))
        assert second is not None

    def test_shock_trigger_debounce_is_per_symbol_not_global(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        open_position(book, "MSFT", "long", 10.0, 250.0)
        orch = _make_orchestrator(book)
        routes = dict(self._GET_ROUTES)
        routes["/research/artifacts"] = [
            {"artifact_id": "art_1", "status": "ACTIVE", "type": "trade_plan"},
            {"artifact_id": "art_2", "status": "ACTIVE", "type": "trade_plan"},
        ]
        msft_plan = {**_SAMPLE_PLAN, "symbol": "MSFT"}
        routes["/research/trade-plan/art_2"] = {"artifact_id": "art_2", "trade_plan_data": json.dumps(msft_plan)}
        routes["/candles/MSFT"] = {"data": [{"close": 251.0}]}
        get_mock, post_mock = _router(routes)
        orch._http.get = get_mock
        orch._http.post = post_mock

        aapl_result = asyncio.run(orch.on_shock_event("AAPL"))
        msft_result = asyncio.run(orch.on_shock_event("MSFT"))

        assert aapl_result is not None
        assert msft_result is not None  # AAPL's debounce does not block MSFT

    def test_shock_trigger_no_matching_active_plan_returns_none(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router({"/research/artifacts": []})
        orch._http.get = get_mock
        orch._http.post = post_mock

        action = asyncio.run(orch.on_shock_event("AAPL"))
        assert action is None


class TestReconciliation:
    def test_drift_detected_and_reported(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, _ = _router(get_routes={
            "/broker/positions": [{"symbol": "AAPL", "qty": 7.0}],
        })
        orch._http.get = get_mock

        report = asyncio.run(orch._reconcile_book_with_broker({"AAPL": 150.0}))

        assert report["drift_detected"] is True
        assert report["n_drifts"] == 1

    def test_no_drift_when_matching(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, _ = _router(get_routes={
            "/broker/positions": [{"symbol": "AAPL", "qty": 10.0}],
        })
        orch._http.get = get_mock

        report = asyncio.run(orch._reconcile_book_with_broker({"AAPL": 150.0}))
        assert report["drift_detected"] is False


class TestFullCycle:
    def test_cycle_enters_new_plan_end_to_end(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/research/artifacts": [{"artifact_id": "art_1", "status": "ACTIVE", "type": "trade_plan"}],
                "/research/trade-plan/art_1": {"artifact_id": "art_1", "trade_plan_data": json.dumps(_SAMPLE_PLAN)},
                "/candles/AAPL": {"data": [{"close": 150.0}]},
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        result = asyncio.run(orch.cycle())

        assert result["status"] == "ok"
        assert len(result["actions"]) == 1
        assert result["actions"][0]["action"] == "entered"
        assert list_open_positions(book, symbol="AAPL")[0].qty > 0

    def test_cycle_skips_when_no_active_plans(self, book) -> None:
        orch = _make_orchestrator(book)
        get_mock, _ = _router(get_routes={"/research/artifacts": []})
        orch._http.get = get_mock

        result = asyncio.run(orch.cycle())

        assert result["status"] == "skipped_no_active_plans"

    def test_cycle_evaluates_existing_position_and_reconciles(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 150.0)
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/research/artifacts": [{"artifact_id": "art_1", "status": "ACTIVE", "type": "trade_plan"}],
                "/research/trade-plan/art_1": {"artifact_id": "art_1", "trade_plan_data": json.dumps(_SAMPLE_PLAN)},
                "/candles/AAPL": {"data": [{"close": 151.0}]},
                "/angle/shock_clustering/AAPL": {"data": []},
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/broker/positions": [{"symbol": "AAPL", "qty": 10.0}],
            },
        )
        orch._http.get = get_mock
        orch._http.post = post_mock

        result = asyncio.run(orch.cycle())

        assert result["status"] == "ok"
        assert result["actions"][0]["action"] == "hold"
        assert result["reconciliation"]["drift_detected"] is False
