import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.book.positions import init_book, list_open_positions, open_position
from vinu_live.breaker.engine import BreakerVerdict
from vinu_live.config import LiveConfig
from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator


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
    orch = TradePlanOrchestrator(config, book=book)
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

    def test_breaker_halt_blocks_invalidation_exit(self, book) -> None:
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
