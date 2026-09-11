"""Pre-live acceptance scenarios (2026-09-11): deterministic, engineered
OHLCV sequences with a KNOWN correct answer, driven through the REAL
`TradePlanOrchestrator` -- no LLM, no real network, no real broker. The
complement to `scripts/run_month_replay.py` (vinu-agent), which replays
real historical data through the real LLM agent and has no fixed
"correct" outcome to assert against; these scenarios exist specifically
so the mechanical pipeline -- entry, the catastrophic backstop, the
trailing-stop ratchet, and an invalidation exit -- can be proven correct
against a known answer before real capital is ever at risk, independent
of whatever an LLM happens to decide on a given day.

Re-verified before writing these (not guessed): the "trailing stop" the
orchestrator computes is BOOKKEEPING ONLY -- `update_stop_loss()`'s own
docstring says so, and `_evaluate_open_position` never compares price
against the ratcheted `stop_loss` to decide an exit. The actual exit
mechanism is two-layered by design (see orchestrator.py's own "Stage 0
(G3)" comment): (1) a static CVaR-sized catastrophic-backstop stop placed
as a REAL resting broker order at entry (protects the position even if
this process is down), and (2) invalidation_conditions/contingency_rules,
evaluated fresh every cycle against live P&L metrics -- the plan's actual,
dynamic exit logic. So "is the trailing stop taken care of properly"
splits into three separately-checkable claims, and that is exactly how
these three scenarios are split.

Reuses the exact same `book` fixture / `_make_orchestrator` / `_router` /
`_resp` helpers `test_trade_plan_orchestrator.py` already established --
these scenarios exercise the real `cycle()` / `_evaluate_open_position()`
code, not a reimplementation, same posture as every other test in this
suite.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from unittest.mock import AsyncMock

import pytest

from vinu_live.book.positions import init_book, list_open_positions, open_position
from vinu_live.config import LiveConfig
from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator
from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue

_ARTIFACT_ID = "art_prelive_1"


# Same small helpers test_trade_plan_orchestrator.py already established --
# duplicated locally rather than cross-file imported (pytest's rootdir/
# testpaths setup here doesn't add tests/ to sys.path the way a plain `cd
# tests && python -c "import ..."` does, so the cross-file import silently
# fails under the real `pytest tests/` invocation this repo actually uses).
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
    orch = TradePlanOrchestrator(config, book=book, rebalance_queue=RebalanceRequestQueue(":memory:"))
    orch._http = AsyncMock()
    return orch


def _resp(status_code=200, json_body=None):
    from unittest.mock import MagicMock

    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


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


def _plan(**overrides) -> dict:
    plan = {
        "symbol": "AAPL",
        "timeframe": "daily",
        "direction": "long",
        "risk_bands": {"max_position_size_pct": 0.05},
        "contingency_rules": [],
        "invalidation_conditions": [],
        "forecast": {"direction": "long", "confidence": 0.6, "magnitude_pct": 0.03, "magnitude_std": 0.02},
    }
    plan.update(overrides)
    return plan


def _bars(closes: list[float]) -> dict:
    return {"data": [{"close": c} for c in closes]}


class TestScenarioEntryPlacesTheRealCatastrophicBackstop:
    """Known-correct answer: given a plan with a CVaR estimate and a fresh
    signal, one cycle() must (a) submit a real order sized off the plan's
    max_position_size_pct, (b) attach a resting stop at
    price*(1-cvar_95_limit) -- the "protected even if this process is
    down" backstop -- and (c) book the resulting open position with the
    correct entry price. This is the whole entry half of "complete
    workflow happening."
    """

    def test_entry_fires_with_correctly_sized_backstop(self, book) -> None:
        plan = _plan(risk_bands={"max_position_size_pct": 0.05, "cvar_95_limit": 0.05})
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/research/artifacts": [{"artifact_id": _ARTIFACT_ID, "status": "ACTIVE", "type": "trade_plan"}],
                f"/research/trade-plan/{_ARTIFACT_ID}": {
                    "artifact_id": _ARTIFACT_ID, "trade_plan_data": json.dumps(plan),
                },
                "/candles/AAPL": _bars([100.0]),
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "entry-1"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())

        assert result["actions"][0]["action"] == "entered"
        order_call = post_mock.await_args_list[0]
        assert order_call.kwargs["json"]["side"] == "buy"
        assert order_call.kwargs["json"]["stop_loss_price"] == 100.0 * (1 - 0.05)  # == 95.0

        open_positions = list_open_positions(book, symbol="AAPL")
        assert len(open_positions) == 1
        assert open_positions[0].avg_entry == 100.0
        assert open_positions[0].side == "long"

    def test_no_cvar_estimate_enters_without_a_backstop_price(self, book) -> None:
        """Fail-open by design (orchestrator.py's own comment): no invented
        stop distance when the plan carries no CVaR estimate -- a plain
        market order, same as the rest of this file's data-quality guards."""
        plan = _plan(risk_bands={"max_position_size_pct": 0.05})  # no cvar_95_limit
        orch = _make_orchestrator(book)
        get_mock, post_mock = _router(
            get_routes={
                "/research/artifacts": [{"artifact_id": _ARTIFACT_ID, "status": "ACTIVE", "type": "trade_plan"}],
                f"/research/trade-plan/{_ARTIFACT_ID}": {
                    "artifact_id": _ARTIFACT_ID, "trade_plan_data": json.dumps(plan),
                },
                "/candles/AAPL": _bars([100.0]),
                "/broker/account": {"configured": True, "equity": 100000.0},
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "entry-2"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock

        result = asyncio.run(orch.cycle())

        assert result["actions"][0]["action"] == "entered"
        order_call = post_mock.await_args_list[0]
        assert order_call.kwargs["json"].get("stop_loss_price") is None


class TestScenarioTrailingStopRatchetsCorrectlyBarByBar:
    """Known-correct answer: on a clean rising sequence, the book's
    stop_loss field must (a) stay None until enough history exists,
    (b) then ratchet strictly upward as price rises, (c) always sit below
    the current price (a sane long stop), and (d) never loosen even on a
    flat/down bar within the sequence. Drives `_evaluate_open_position`
    bar by bar -- the same real trailing_stop_for() + ratchet-guard code
    `cycle()` calls internally, isolated from a full plan re-fetch each
    bar (existing test-suite convention)."""

    def test_stop_ratchets_up_and_never_loosens(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        # Invalidation set unreachable on purpose -- this scenario isolates
        # the trailing ratchet from the exit-triggering scenario below.
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.90, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)

        closes = [100.0, 101.0, 103.0, 102.5, 106.0, 110.0, 109.0, 115.0]
        seen_stops: list[float | None] = []
        for i in range(1, len(closes) + 1):
            window = closes[:i]
            get_mock, post_mock = _router(
                get_routes={"/candles/AAPL": _bars(window)},
                post_routes={"/broker/order": {"status": "submitted", "order_id": f"o{i}"}},
            )
            orch._http.get, orch._http.post = get_mock, post_mock
            position = list_open_positions(book, symbol="AAPL")[0]

            action = asyncio.run(orch._evaluate_open_position(plan, position, window[-1], 100000.0))

            # Found while writing this scenario, not assumed going in: once
            # the ratcheted stop implies a full 1R gain, a SEPARATE,
            # legitimate mechanism ("Bracket 50% at 1R") takes a partial
            # profit -- also correct behavior, not the invalidation exit
            # this scenario is isolating against. Either is a pass here.
            assert action["action"] in ("hold", "bracket_partial"), f"bar {i}: unexpected action {action}"
            seen_stops.append(list_open_positions(book, symbol="AAPL")[0].stop_loss)

        # Needs >= 3 closes -- the first two bars can't compute an ATR yet.
        assert seen_stops[0] is None
        assert seen_stops[1] is None
        populated = [s for s in seen_stops if s is not None]
        assert len(populated) >= 3

        # Ratchet-only: every populated value is >= the previous populated
        # value (never loosens), and strictly increases at least once
        # (the sequence trends up, so the stop must actually move).
        assert all(populated[i] >= populated[i - 1] for i in range(1, len(populated)))
        assert any(populated[i] > populated[i - 1] for i in range(1, len(populated)))

        # Sane long stop: always below the price it was computed against.
        for i, stop in enumerate(seen_stops):
            if stop is not None:
                assert stop < closes[i]


class TestScenarioInvalidationFiresTheRealExit:
    """Known-correct answer: an adverse move past the plan's own
    invalidation threshold must submit a real reduce_only exit order and
    close the book position -- the actual, dynamic exit mechanism
    (distinct from the bookkeeping-only trailing stop above)."""

    def test_adverse_move_past_threshold_exits_and_closes_the_book(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)
        # -10% move -- past the -8% threshold.
        get_mock, post_mock = _router(
            get_routes={
                "/candles/AAPL": _bars([100.0, 98.0, 95.0, 90.0]),
                "/broker/positions": [],
            },
            post_routes={"/broker/order": {"status": "submitted", "order_id": "exit-1"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        action = asyncio.run(orch._evaluate_open_position(plan, position, 90.0, 100000.0))

        assert action["action"] == "invalidation_exit"
        order_call = post_mock.await_args_list[0]
        assert order_call.kwargs["json"]["side"] == "sell"
        assert order_call.kwargs["json"]["reduce_only"] is True
        assert list_open_positions(book, symbol="AAPL") == []

    def test_move_short_of_the_threshold_holds_instead(self, book) -> None:
        open_position(book, "AAPL", "long", 10.0, 100.0)
        plan = _plan(invalidation_conditions=[
            {"metric": "unrealized_pnl_pct", "operator": "<=", "threshold": -0.08, "action": "exit", "action_params": {}},
        ])
        orch = _make_orchestrator(book)
        # -5% move -- short of the -8% threshold, must NOT exit.
        get_mock, post_mock = _router(
            get_routes={"/candles/AAPL": _bars([100.0, 98.0, 96.0, 95.0])},
            post_routes={"/broker/order": {"status": "submitted", "order_id": "should-not-fire"}},
        )
        orch._http.get, orch._http.post = get_mock, post_mock
        position = list_open_positions(book, symbol="AAPL")[0]

        action = asyncio.run(orch._evaluate_open_position(plan, position, 95.0, 100000.0))

        assert action["action"] != "invalidation_exit"
        post_mock.assert_not_awaited()
        assert len(list_open_positions(book, symbol="AAPL")) == 1
