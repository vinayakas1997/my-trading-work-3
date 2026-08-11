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
